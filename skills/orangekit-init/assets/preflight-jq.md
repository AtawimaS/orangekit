<!-- An asset used only by orangekit-init. Called from Step 0.5 of SKILL.md. Needed only when jq is missing, so it was taken out of the body. -->

# Step 0.5: Environment check — jq

This harness's verification hook (`build-gate`) and `doctor --graph` only work fully when `jq` is
present. Without it the plugin still installs and runs, but both safeguards **degrade silently,
without a single error** (macOS does not ship it, and Windows does not include it in Git Bash either).

```bash
command -v jq >/dev/null 2>&1 && jq --version || echo "MISSING"
```

- **If present**, move on to Step 1 without saying anything.
- **If missing**, say so briefly and ask whether to install it (a plain confirmation is enough — do
  not spend `AskUserQuestion` budget):

  > "`jq` is missing, so build verification and graph verification start in a degraded state. Install it now?"

  Detect the package manager and pick the command (use the first one found):

  | Detected | Install command |
  | --- | --- |
  | `command -v brew` | `brew install jq` |
  | `command -v winget` | `winget install --id jqlang.jq -e --source winget` |
  | `command -v apt-get` | `sudo apt-get install -y jq` |
  | `command -v dnf` | `sudo dnf install -y jq` |
  | `command -v apk` | `apk add jq` |
  | none of the above | cannot automate — point to https://jqlang.org/download/ and skip |

  For paths that need `sudo`, first try `sudo -n <command>` without a password. If that fails
  (a password prompt would freeze the tool), **give up on running it** and merely tell the user
  the command to run in their own terminal, then move to the next step.

  A refusal or a failed install **does not block initialization** — say "Continuing without the
  install. You can install it later with `<command>`" and proceed to Step 1.

  This step covers **the `jq` install only**. If the check itself behaves strangely on Windows
  (command not found, and so on), the cause may be a missing Git Bash, which is not what this step
  fixes — point to [`docs/windows-setup.md`](../../docs/windows-setup.md).
