#!/usr/bin/env python
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
        self.trials = Trials()

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
    def __init__(self):
        pass

    def blocks(self):
        blocks = [block.itertuples()
                  for _, block in self.trials.groupby('category')]
        self.random.shuffle(blocks)
        return blocks


if __name__ == '__main__':
    subj = dict(name='test')
    exp = Experiment(subj)
    exp.run()
