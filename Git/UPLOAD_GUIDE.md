# Upload the complete history to GitHub

The bundle contains the saved project history. Uploading today can transfer all existing commits in one push. Commit dates describe saved changes; they do not prove that the repository was uploaded on those dates.

## 1. Create the repository

Sign in to your GitHub account and create an empty repository. Do not add a README, license or .gitignore during repository creation. Copy its HTTPS URL. If the repository is private, give the instructor access.

## 2. Clone the local bundle

Open PowerShell or Git Bash in the extracted project folder:

```text
git clone Git/SE431-project.bundle SE431-repository
cd SE431-repository
git branch -M main
git log --oneline --reverse
```

The log should contain the six original course stages, two correction commits and the current delivery update. The existing authors and recorded dates are preserved.

## 3. Connect and push once

Replace the example URL with the URL of your empty repository:

```text
git remote set-url origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Git may ask you to sign in. Use your normal GitHub authentication. This push transfers the saved history reachable from main.

## 4. Check the submission

Open the repository page. Check the files and commit history, confirm instructor access, and add the real repository URL to the report and presentation before submission.

For new work, each team member should use their own verified Git name and email. Keep the existing commit authors and dates. Add new commits for real changes instead of replacing the saved history.

References:
- https://git-scm.com/docs/git-push
- https://docs.github.com/en/pull-requests/reference/commits
