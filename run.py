#!/usr/bin/env python
import socket

from numpy import random
import pandas
from psychopy import visual, core, sound, gui, logging, data
from unipath import Path
import yaml

try:
    import pygame
except ImportError:
    print 'pygame not found! can\'t use gamepad'


DATA_COLS = ('subj_id date experimenter computer block_ix trial_ix sound word '
             'response correct_response rt').split()
DATA_FILE = 'data/{subj_id}.csv'


class Experiment(object):
    delay_sec = 0.6

    def __init__(self, subject):
        self.session = subject.copy()
        self.session['date'] = data.getDateStr()
        self.session['computer'] = socket.gethostname()
        self.trials = Trials(**subject)
        self.load_sounds('stimuli/sounds')
        self.texts = yaml(open('texts.yaml'))
        self.device = ResponseDevice(gamepad=None,
                                     keyboard=dict(y='yes', n='no'))

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
            self.run_block(block)
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
        visual.TextStim(self.win, title).draw()
        visual.TextStim(self.win, body).draw()
        self.win.flip()
        event.waitKeys()

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
    messages = pandas.read_csv('stimuli/messages.csv')

    def __init__(self, seed=None, **kwargs):
        self.random = random.RandomState(seed=seed)

        blocks = [1, 2, 3, 4]
        def assign_block(chunk):
            block_ix = self.random.choice(blocks, size=len(chunk),
                                          replace=False)
            chunk.insert(0, 'block_ix', block_ix)
            return chunk

        seeds = (self.messages[['word_category', 'seed_id']]
                     .drop_duplicates()
                     .groupby('word_category')
                     .apply(assign_block)
                     .sort(['block_ix', 'word_category', 'seed_id'])
                     .reset_index(drop=True))

        words = (self.messages[['seed_id', 'word']]
                     .drop_duplicates())

        def assign_word(seed_id):
            available_ix = words.index[words.seed_id == seed_id].tolist()
            selected_ix = self.random.choice(available_ix, size=1,
                                             replace=False)
            selected = words.ix[selected_ix, 'word'].squeeze()
            words.drop(selected_ix, inplace=True)
            return selected

        seeds['word'] = seeds.seed_id.apply(assign_word)
        self.seeds = seeds


class ResponseDevice(object):
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

        return (response, rt)

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
        key, rt = event.waitKeys(self.keyboard.keys(),
                                 timeStamped=self.timer)[0]
        response = self.keyboard[key]
        return (response, rt * 1000)


if __name__ == '__main__':
    subj = dict(subj_id='test', experimenter='test', seed=100)
    exp = Experiment(subj)
    exp.run()
