---
workflow: general-video
flow: automation
storyboard: no
message: "jn reads and writes JobNimbus from the terminal, and you can preview every write first"
destination: github-readme
aspect: 1280x720
language: en
length: 14s
---

## Intent

A short, silent, seamlessly looping GIF for the top of the JobNimbus CLI README.
One terminal window runs three real `jn` commands: a filtered read, a
`--dry-run` write preview, and a real write (`add-note`). It should show at a
glance that the tool is read + write and that writes can be previewed.

## Customizations

- Output is a GIF (`assets/demo.gif` in the repo), 15 fps, infinite loop.
- First and last frame match so the loop has no jump.

## Notes

- Public README: every name, id and count on screen is invented. No real
  customer data from the JobNimbus account.
- Command lines and output formats match what `jn` 0.3.0 actually prints.
- Palette follows the repo logo: near-black with one blue accent.
- `flow` / `storyboard` were not asked; they are defaults chosen for a 14s,
  three-beat piece. Typing engine adapted from the registry component
  `code-terminal-run` (one persistent window instead of three mounts).
