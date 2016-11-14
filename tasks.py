import sys

from invoke import task
from unipath import Path
import pandas

from run import Experiment, Trials


@task(help=dict(install='(Re)install the wordsintransition pkg.'))
def select_sounds(ctx, install=False, keep=None):
    """Select the sounds to use in this experiment."""
    if install:
        R_cmd = 'devtools::install_github("lupyanlab/words-in-transition", subdir = "wordsintransition")'
        ctx.run("Rscript -e '{}'".format(R_cmd))

    ctx.run('Rscript R/select_messages.R')

    if not keep:
        ctx.run('rm -f Rplots.pdf')
    else:
        ctx.run('mv Rplots.pdf {}'.format(keep))

@task
def copy_sounds(ctx, force=False):
    """Copy sounds from acoustic-similarity to use in this experiment."""
    src_dir = Path('../acoustic-similarity/data/sounds')
    assert src_dir.isdir(), 'expecting sounds to be in {}'.format(src_dir)

    dst_dir = Path('stimuli/sounds')

    if not dst_dir.isdir():
        dst_dir.mkdir()

    trials = pandas.read_csv('stimuli/messages.csv')
    for seed_id in trials.seed_id.unique():
        seed_name = '{}.wav'.format(seed_id)
        dst = Path(dst_dir, seed_name)
        if force or not dst.exists():
            Path(src_dir, seed_name).copy(dst)

@task
def create_trials(ctx, seed=None, word_type_n=None):
    """Create a sample trial list."""
    subj_vars = dict(seed=int(seed), word_type_n=int(word_type_n))
    Trials(**subj_vars).trials.to_csv('sample_trials.csv', index=False)


@task
def open_survey(ctx):
    """Open the survey to test out how values are prepopulated."""
    subj = dict(subj_id='test', word_type_n=1)
    exp = Experiment(subj)  # creates blank data file
    exp.open_survey()
    exp.remove_data_file()  # removes blank data file
