#!/usr/bin/env python
from numpy import random
import pandas
from psychopy import visual, core, sound, gui
from unipath import Path


TITLE = "Learn the names of different sounds"
INSTRUCTIONS = """\
"""
BREAK = ""

DATA_COLS = ('subj_id exp_start block_ix trial_ix sound word '
             'response correct_response rt').split()

DATA_DIR = Path('data')
if not DATA_DIR.isdir():
    DATA_DIR.mkdir()
DATA_FILE = Path(DATA_DIR, '{subj_id}.csv')


class Experiment(object):

    def __init__(self, subject):
        self.subject = subject
        self.trials = Trials(**subject)
        sounds = load_sounds('stimuli/sounds')
        self.data_file = open(DATA_FILE.format(**subject), 'w', 0)

    def run(self):
        """Run the experiment."""
        self.show_instructions()

        for block in self.trials.blocks():
            self.run_block(block)
            self.show_break_screen()

        self.data_file.close()
        core.quit()

    def run_block(self, block):
        """Run a block of trials."""
        for trial in block:
            self.run_trial(trial)

    def run_trial(self, trial):
        """Run a single trial."""
        # Play sound
        # Show word
        # Get response
        response = dict()
        self.write_trial(**response)

    def show_instructions(self):
        pass

    def show_break_screen(self):
        pass

    def write_trial(self, **response):
        pass


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


def load_sounds(sounds_dir):
    """Create a dict of sound_name -> sound_obj."""
    sounds = {}
    for snd in Path(sounds_dir).listdir('*.wav'):
        sounds[snd.name] = sound.Sound(snd)
    return sounds


if __name__ == '__main__':
    subj = dict(name='test')
    exp = Experiment(subj)
    exp.run()
