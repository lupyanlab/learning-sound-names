#!/usr/bin/env python
import socket

from numpy import random
import pandas
from psychopy import visual, event, core, sound, gui, logging, data
from unipath import Path
import yaml

try:
    import pygame
except ImportError:
    print 'pygame not found! can\'t use gamepad'


DATA_COLS = ('subj_id date experimenter computer block_ix trial_ix '
             'sound_id sound_category word word_category correct_response '
             'response rt is_correct').split()
DATA_FILE = 'data/{subj_id}.csv'


class Experiment(object):
    delay_sec = 0.6

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
            except QuitExperiment:
                break
            else:
                self.show_break_screen()

        self.data_file.close()
        core.quit()

    def setup_window(self):
        self.win = visual.Window()
        self.word = visual.TextStim(self.win)

    def run_block(self, block):
        """Run a block of trials."""
        for trial in block:
            self.run_trial(trial)

    def run_trial(self, trial):
        """Run a single trial."""
        self.word.setText(trial.word)
        sound_duration = self.sounds[trial.sound].getDuration()

        # Start trial
        self.win.flip()

        # Play sound
        self.sounds[trial.sound].play()
        core.wait(sound_duration)

        # Delay between sound offset and word onset
        core.wait(self.delay_sec)

        # Show word and get response
        self.word.draw()
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
        self.show_text_screen(title=self.texts['title'],
                              body=self.texts['instructions'])

    def show_break_screen(self):
        title = "Take a break!"
        body = ("Take a quick break. When you are ready to continue, "
                "press the SPACEBAR.")
        self.show_text_screen(title=title, body=body)

    def show_text_screen(self, title, body):
        text_kwargs = dict(win=self.win, font='Consolas',
                           wrapWidth=self.win.size[0] * 0.7)
        gap = 80
        title_y = self.win.size[1]/2 - gap
        visual.TextStim(text=title, alignVert='top',
                        pos=[0, title_y], height=30, bold=True,
                        **text_kwargs).draw()
        visual.TextStim(text=body, alignVert='top', height=20,
                        pos=[0, title_y-gap],
                        **text_kwargs).draw()
        self.win.flip()
        response = event.waitKeys()[0]
        if response == 'q':
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
            self.sounds[snd.name] = sound.Sound(snd)


class Trials(object):
    def __init__(self, seed=None, **kwargs):
        self.random = random.RandomState(seed=seed)
        self._messages = None
        self._trials = None

    @property
    def messages(self):
        """All eligible messages that could be tested in this experiment."""
        if self._messages is None:
            self._messages = pandas.read_csv('stimuli/messages.csv')
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
                     .rename(columns={'category': 'seed_category'}))

        block_ixs = [1, 2, 3, 4]
        def assign_block(chunk):
            ix = self.random.choice(block_ixs, size=len(chunk), replace=False)
            chunk.insert(0, 'block_ix', ix)
            return chunk

        return (seeds.groupby('seed_category')
                     .apply(assign_block)
                     .sort_values(['block_ix', 'seed_category', 'seed_id'])
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
        n_sound_rep = 4     # Number of times each sound is heard in a block
        prop_correct = 0.5  # Proportion trials for which 'yes' is correct

        # Begin by making trials as long as necessary
        trials = pandas.concat([blocks] * n_sound_rep, ignore_index=True)

        # Randomly decide whether the trial is correct or incorrect
        trials['correct_response'] = \
            self.random.choice([1, 0], size=len(trials),
                               p=[prop_correct, 1-prop_correct])

        # Assign a word for each trial based on desired correctness
        def determine_word(trial):
            if trial.correct_response:
                options = words.word_category == trial.seed_category
            else:
                options = words.word_category != trial.seed_category

            return (words.ix[options, 'word']
                         .sample(1, random_state=self.random)
                         .squeeze())

        trials['word'] = trials.apply(determine_word, axis=1)
        trials = trials.merge(words[['word', 'word_category']])

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
    """Provides a common interface for both gamepad and keyboard responses.

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
        except:
            print 'unable to init joystick with pygame'
            self.stick = None

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
                        rt =  self.timer.getTime() * 1000
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
    subj = dict(subj_id='test', experimenter='test', seed=100)
    exp = Experiment(subj)
    exp.run()
