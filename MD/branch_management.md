# Branch Management Guide

A practical reference for managing git branches and coordinating work across local and cluster environments.

---

## Git Setup and Navigation

### Initial Repository Setup

**`git clone git@github.com:VU-IVM/Criticality-Analysis-Roads-Serbia.git`**
- Downloads the repository from GitHub to your computer for the first time.
- Run once per machine to get started.

**`cd Criticality-Analysis-Roads-Serbia`**
- Changes into the repository folder so following commands apply to that project.
- Do this before running any other git commands.

### Working with Branches

**`git checkout main`**
- Switches to the main branch (the stable baseline for this project).
- Use when you want to return to the main codebase.

**`git checkout -b feature/your-feature-name`**
- Creates a new branch and switches to it immediately.
- Use for isolated work on a single feature or task.
- Example: `git checkout -b feature/yml-improvement`

**`git checkout feature/your-feature-name`**
- Switches to an existing branch you want to work on or update.
- Use to move between branches after they're created.

### Fetching and Pulling

**`git fetch origin`**
- Downloads the latest branch and commit information from the remote without changing your local files.
- Use before checking what's new upstream.

**`git pull`**
- Fetches remote changes and merges them into your current local branch.
- Use to sync your branch with the remote version.

**`git pull --ff-only`**
- Updates your branch only if Git can move it forward without creating a merge commit.
- Use when you expect a clean sync and want to avoid accidental merge history.

---

## Inspecting and Committing Changes

### Checking Your Work

**`git status`**
- Shows what files you changed, added, or have not staged yet.
- Run before committing to see exactly what will go in.

### Staging and Committing

**`git add BRANCH_MANAGEMENT.md`**
- Stages that file so Git includes it in the next commit.
- Use when you're ready to save specific changes.

**`git commit -m "Improve branch management instructions"`**
- Creates a commit from your staged changes with a descriptive message.
- Use to record a logical step of work with context.

### Publishing Changes

**`git push -u origin feature/your-feature-name`**
- Sends your branch to GitHub and sets the upstream tracking branch.
- Use the first time you publish a new branch (the `-u` flag sets tracking).

**`git push`**
- Sends later commits on the current branch to the remote.
- Use after new commits are ready to share.

---

## Syncing Between Local and Cluster

### Accessing the Cluster

**`ssh your-cluster`**
- Opens a shell session on the remote cluster machine.
- Use to work on cluster jobs or access cluster data directly.

### Syncing Code to Cluster

**`rsync -av --exclude '.git' --exclude 'pycache' ./ user@cluster:~/projects/Criticality-Analysis-CR/`**
- Synchronizes files from local to cluster efficiently without git history.
- Use when you need to copy code or small config files.
- Much faster than pushing/pulling large git histories.

### Syncing Results Back to Local

**`rsync -av user@cluster:~/projects/Criticality-Analysis-CR/results/ ./results/`**
- Copies results from the cluster back to your local machine.
- Use for logs, outputs, and reports after cluster jobs complete.

---

## Running Work on the Cluster

### Batch Jobs

**`sbatch train_model.sh`**
- Submits a SLURM batch job to the cluster scheduler.
- Use for long-running training, preprocessing, or analysis jobs.
- Jobs run in the background; check status with `squeue`.

### Interactive Scripts

**`python predict_model.py`**
- Runs a Python script directly.
- Use when the job is short enough to run interactively or inside a job script.

---

## Tracking Reproducibility

### Recording Commit States

**`git rev-parse HEAD`**
- Prints the exact commit hash (SHA) of your current code state.
- Use to record the version used for an experiment in your lab notebook.

### Creating Tags

**`git tag run-2026-07-16`**
- Creates a named tag for the current commit.
- Use to mark a version you want to come back to later (e.g., a good experiment).

**`git push origin run-2026-07-16`**
- Publishes that tag to GitHub.
- Use so the tag is available when working from other machines.

---

## Quick Reference Cheat Sheet

| Task | Command |
|------|---------|
| Clone repo | `git clone git@github.com:VU-IVM/Criticality-Analysis-Roads-Serbia.git` |
| Create branch | `git checkout -b feature/name` |
| Switch branch | `git checkout branch-name` |
| Check status | `git status` |
| Stage file | `git add filename` |
| Commit | `git commit -m "message"` |
| Push (first time) | `git push -u origin branch-name` |
| Push (later) | `git push` |
| Pull updates | `git pull` or `git pull --ff-only` |
| Fetch updates | `git fetch origin` |
| Tag version | `git tag tagname` |
| Get commit hash | `git rev-parse HEAD` |
| Sync to cluster | `rsync -av --exclude '.git' --exclude 'pycache' ./ user@cluster:~/path/` |
| Sync from cluster | `rsync -av user@cluster:~/path/results/ ./results/` |
| Submit cluster job | `sbatch job.sh` |

---

## Typical Workflow: Day-to-Day

### Starting work on a new feature

```bash
git fetch origin
git checkout -b feature/my-feature
```

### Making changes

```bash
# ... edit files ...
git status              # Check what changed
git add file1 file2     # Stage your changes
git commit -m "Add my feature"
git push -u origin feature/my-feature  # First push
```

### Subsequent pushes

```bash
# ... more edits ...
git add file3
git commit -m "Refine feature"
git push                # Subsequent pushes (simpler)
```

### Syncing to cluster before running

```bash
git push                # Push to GitHub first
ssh cluster
cd ~/projects/Criticality-Analysis-CR
git pull                # Get latest in cluster
rsync -av user@local:~/project/ ./  # Or rsync from local if needed
sbatch job.sh           # Run cluster job
```

### Getting results back

```bash
rsync -av user@cluster:~/projects/Criticality-Analysis-CR/results/ ./results/
# View results locally
```

### Recording a good state

```bash
git tag experiment-v1
git push origin experiment-v1
git rev-parse HEAD     # Save the hash in your notebook
```

---

## Notes

- Always run `git status` before committing to verify you're saving what you intend.
- Use `git fetch` frequently to stay aware of remote changes without disrupting your work.
- Prefer `git pull --ff-only` to avoid unexpected merge commits.
- Tag important experiment states so you can reproduce them later.
- Use `rsync` for large data files or results; don't commit them to git.
