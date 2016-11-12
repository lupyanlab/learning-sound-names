#!/usr/bin/env python
import socket

from psychopy import visual, event, core, sound, gui, logging, data
import pandas
from numpy import random
from unipath import Path
import yaml

try:
    import pygame
except ImportError:
    print "pygame not found! can't use gamepad"

DATA_COLS = """
subj_id date experimenter computer block_ix trial_ix
sound_id word sound_category word_category word_type
correct_response response rt is_correct
""".split()
DATA_FILE = 'data/{subj_id}.csv'

# Between subject variables
WORD_TYPES = {1: 'sound_effect',
              2: 'first_gen_imitation',
              3: 'last_gen_imitation'}


class Experiment(object):
    fix_sec = 0.2
    delay_sec = 0.6
    word_sec = 0.5
    quit_allowed = True

    def __init__(self, subject):
        self.session = subject.copy()
        self.session['date'] = data.getDateStr()
        self.session['computer'] = socket.gethostname()

        self.trials = Trials(**subject)
        self.load_sounds('stimuli/sounds')
        self.feedback = {0: sound.Sound('stimuli/feedback/buzz.wav'),
                         1: sound.Sound('stimuli/feedback/bleep.wav')}
        self.texts = yaml.load(open('texts.yaml'))
        self.device = ResponseDevice(gamepad=None,
                                     keyboard=dict(y=1, n=0))

        data_dir = Path(DATA_FILE.format(**subject)).parent
        if not data_dir.isdir():
            data_dir.mkdir()
        self.data_file = open(DATA_FILE.format(**subject), 'w', 0)
        self.write_trial()  # write header

    def run(self):
        """Run the experiment."""
        self.setup_window()
        self.show_instructions()

        for block in self.trials.blocks():
            try:
                self.run_block(block)
                self.show_break_screen()
            except QuitExperiment:
                break

        self.data_file.close()
        core.quit()

    def setup_window(self):
        self.win = visual.Window(fullscr=True, units='pix', allowGUI=False)

        text_kwargs = dict(win=self.win, height=50, font='Consolas',
                           color='black')
        self.word = visual.TextStim(**text_kwargs)
        self.fix = visual.TextStim(text='+', **text_kwargs)
        self.prompt = visual.TextStim(text='?', **text_kwargs)

        self.icon = visual.ImageStim(self.win, 'stimuli/speaker_icon.png')

    def run_block(self, block):
        """Run a block of trials."""
        for trial in block:
            self.run_trial(trial)

    def run_trial(self, trial):
        """Run a single trial."""
        self.word.setText(trial.word)
        sound_sec = self.sounds[trial.sound_id].getDuration()

        # Start trial
        self.fix.draw()
        self.win.flip()
        core.wait(self.fix_sec)

        # Play sound
        self.icon.draw()
        self.win.flip()
        self.sounds[trial.sound_id].play()
        core.wait(sound_sec)

        # Delay between sound offset and word onset
        self.win.flip()
        core.wait(self.delay_sec)

        # Flash word
        self.word.draw()
        self.win.flip()
        core.wait(self.word_sec)

        # Get response
        self.prompt.draw()
        self.win.flip()
        response = self.device.get_response()

        # Evaluate response
        is_correct = response['response'] == trial.correct_response
        self.feedback[is_correct].play()
        response['is_correct'] = is_correct

        # End trial
        self.win.flip()
        response.update(trial._asdict())  # combine response and trial data
        self.write_trial(**response)

    def show_instructions(self):
        title = 'Learning names for sounds'
        body = self.texts['instructions'].format(**self.device.current_device)
        self.show_text_screen(title=title, body=body)

    def show_break_screen(self):
        title = "Take a break!"
        body = self.texts['break'].format(**self.device.current_device)
        self.show_text_screen(title=title, body=body)

    def show_text_screen(self, title, body):
        text_kwargs = dict(win=self.win, font='Consolas', color='black',
                           wrapWidth=self.win.size[0] * 0.5)
        gap = 80
        title_y = self.win.size[1]/2 - gap
        visual.TextStim(text=title, alignVert='top',
                        pos=[0, title_y], height=40, bold=True,
                        **text_kwargs).draw()
        visual.TextStim(text=body, alignVert='top', height=30,
                        pos=[0, title_y-gap],
                        **text_kwargs).draw()
        self.win.flip()
        response = event.waitKeys()[0]

        if response == 'q' and self.quit_allowed:
            raise QuitExperiment

    def write_trial(self, **trial_data):
        data = self.session.copy()
        if trial_data:
            data.update(trial_data)
            row = [data.get(name, '') for name in DATA_COLS]
        else:
            row = DATA_COLS  # write header

        self.data_file.write(','.join(map(str, row))+'\n')

    def load_sounds(self, sounds_dir):
        self.sounds = {}
        for snd in Path(sounds_dir).listdir('*.wav'):
            sound_id = int(snd.stem)
            self.sounds[sound_id] = sound.Sound(snd)


class Trials(object):
    n_sound_rep = 6     # Number of times each sound is heard in a block
    prop_correct = 0.5  # Proportion trials for which 'yes' is correct

    def __init__(self, seed=None, word_type_n=None, **kwargs):
        self.random = random.RandomState(seed=seed)
        assert word_type_n in WORD_TYPES, \
            'word_type_n {} not in {}'.format(word_type_n, WORD_TYPES.keys())
        self.word_type = WORD_TYPES[word_type_n]
        self._messages = None
        self._trials = None

    @property
    def messages(self):
        """All eligible messages that could be tested in this experiment."""
        if self._messages is None:
            self._messages = pandas.read_csv('stimuli/messages.csv')
            # Select only those messages with the correct message type
            selected = self._messages.word_type == self.word_type
            self._messages = self._messages.ix[selected].reset_index(drop=True)
        return self._messages

    @property
    def trials(self):
        """Trials generated for an individual participant."""
        if self._trials is None:
            blocks = self.assign_seeds_by_block()
            words = self.assign_words()
            self._trials = self.generate_trials(blocks, words)
        return self._trials

    def assign_seeds_by_block(self):
        """Assign seeds of the same category to different blocks.

        There are 4 categories of 4 seed messages to divide among
        4 blocks, as each block has a single seed from each category.
        """
        seeds = (self.messages[['seed_id', 'category']]
                     .drop_duplicates()
                     .rename(columns={'seed_id': 'sound_id',
                                      'category': 'sound_category'}))

        block_ixs = [1, 2, 3, 4]
        def assign_block(chunk):
            ix = self.random.choice(block_ixs, size=len(chunk), replace=False)
            chunk.insert(0, 'block_ix', ix)
            return chunk

        return (seeds.groupby('sound_category')
                     .apply(assign_block)
                     .sort_values(['block_ix', 'sound_category', 'sound_id'])
                     .reset_index(drop=True))

    def assign_words(self):
        """Assign a single word to learn for each category.

        Each participant learns the meaning of 4 different words,
        one for each category, over the course of 4 blocks of trials.
        """
        return (self.messages.rename(columns={'category': 'word_category'})
                    .groupby('word_category')
                    .apply(lambda x: x.sample(1, random_state=self.random))
                    .reset_index(drop=True))

    def generate_trials(self, blocks, words):
        """Generate correct and incorrect response trials for each block."""
        # Begin by making trials as long as necessary
        trials = pandas.concat([blocks] * self.n_sound_rep, ignore_index=True)

        # Randomly decide whether the trial is correct or incorrect
        trials['correct_response'] = \
            self.random.choice([1, 0], size=len(trials),
                               p=[self.prop_correct, 1-self.prop_correct])

        # Assign a word for each trial based on desired correctness
        def determine_word(trial):
            if trial.correct_response:
                options = words.word_category == trial.sound_category
            else:
                options = words.word_category != trial.sound_category

            return (words.ix[options, 'word']
                         .sample(1, random_state=self.random)
                         .squeeze())

        trials['word'] = trials.apply(determine_word, axis=1)
        trials = trials.merge(words[['word', 'word_category', 'word_type']])

        # Create trial ix and shuffle within blocks
        def shuffle_trial_ix(block):
            ixs = block.trial_ix.tolist()
            self.random.shuffle(ixs)
            block['trial_ix'] = ixs
            return block

        trials = trials.sort_values('block_ix')
        trials.insert(1, 'trial_ix', range(1, len(trials) + 1))
        trials = (trials.groupby('block_ix')
                        .apply(shuffle_trial_ix)
                        .sort_values(['block_ix', 'trial_ix'])
                        .reset_index(drop=True))

        return trials

    def blocks(self):
        for _, block in self.trials.groupby('block_ix'):
            yield block.itertuples()


class ResponseDevice(object):
    """Provides a common interface for gamepad and keyboard responses.

    When a response device is created, it tries to use the gamepad, but if
    a gamepad cannot be found, it will fall back to using the keyboard.
    Response data is provided as a dict.

    >>> device = ResponseDevice(gamepad={6: 'yes', 7: 'no'},
                                keyboard={'y': 'yes', 'n': 'no'})
    >>> device.get_response()  # tries to use gamepad, otherwise uses keyboard
    {'rt': 1323, 'response': 'yes'}
    """
    def __init__(self, gamepad=None, keyboard=None):
        self.stick = None
        self.gamepad = gamepad
        self.keyboard = keyboard
        self.timer = core.Clock()

        try:
            self.stick = pygame.joystick.init()
            self.stick = pygame.joystick.Joystick(0)
            self.stick.init()
            self.current_device = dict(
                device='gamepad',
                yes_key='green button',
                no_key='red button',
                continue_key='green button',
            )
        except:
            print 'unable to init joystick with pygame'
            self.stick = None
            self.current_device = dict(
                device='keyboard',
                yes_key="'y' key",
                no_key="'n' key",
                continue_key="SPACEBAR",
            )

    def get_response(self):
        if self.stick:
            return self.get_gamepad_response()
        else:
            return self.get_keyboard_response()

    def get_gamepad_response(self):
        responded = False
        response, rt = '*', '*'

        pygame.event.clear()
        self.timer.reset()

        while not responded:
            for event in pygame.event.get():
                if event.type in [pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION]:
                    button = self._get_joystick_responses()
                    if button in self.gamepad:
                        response = self.gamepad[button]
                        rt = self.timer.getTime() * 1000
                        responded = True
                        break

        return dict(response=response, rt=rt)

    def _get_joystick_responses(self):
        for n in range(self.stick.get_numbuttons()):
            if self.stick.get_button(n):
                return n
        for n in range(self.stick.get_numhats()):
            return self.stick.get_hat(n)

    def get_keyboard_response(self):
        responded = False
        response, rt = '*', '*'
        self.timer.reset()
        key, rt = event.waitKeys(keyList=self.keyboard.keys(),
                                 timeStamped=self.timer)[0]
        response = self.keyboard[key]
        return dict(response=response, rt=rt*1000)


class QuitExperiment(Exception):
    pass


if __name__ == '__main__':
    subj = dict(subj_id='test', experimenter='test', seed=100,
                word_type_n=1)
    exp = Experiment(subj)
    exp.run()
