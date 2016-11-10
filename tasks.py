import sys

from invoke import task
from unipath import Path

from run import Trials


@task
def select_sounds(ctx):
    """Select the sounds to use in this experiment."""
    ctx.run('Rscript R/select_messages.R')

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
def create_trials(ctx):
    """Create a sample trial list."""
    Trials().trials.to_csv('sample_trials.csv', index=False)
