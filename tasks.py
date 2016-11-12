import sys

from invoke import task
from unipath import Path

from run import Trials


@task(help=dict(install='(Re)install the wordsintransition pkg first.'))
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
def copy_sounds(ctx):
    """Copy sounds from acoustic-similarity to use in this experiment."""
    src_dir = Path('../acoustic-similarity/data/sounds')
    dst_dir = Path('stimuli/sounds')

    if not dst_dir.isdir():
        dst_dir.mkdir()

    trials = Trials()
    for seed_id in trials.messages.seed_id.unique():
        seed_name = '{}.wav'.format(seed_id)
        dst = Path(dst_dir, seed_name)
        if not dst.exists():
            Path(src_dir, seed_name).copy(dst)

@task
def create_trials(ctx, seed=None, word_type_n=None):
    """Create a sample trial list."""
    subj_vars = dict(seed=seed, word_type_n=int(word_type_n))
    Trials(**subj_vars).trials.to_csv('sample_trials.csv', index=False)
