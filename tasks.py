from invoke import task

@task
def select_sounds(ctx):
    """Select the sounds to use in this experiment."""
    ctx.run('Rscript R/select_messages.R')
