# Watching a roll, for the first time

You are watching AssemblyZero build software from a GitHub issue with no
human in the loop. What is scrolling past is called a roll: one issue,
drawn through a pipeline of stages, end to end.

Three things to know while you watch:

1. **The pipeline is a graph.** Each `NODE [n/total]` line is the run
   entering one node of it: loading the issue, reading the codebase,
   checking the requirements agree with each other, drafting, validating,
   adversarial review by a second model, finalizing. The `NEXT` line
   tells you where it can go from here and why.
2. **A refusal is the system working.** Gates refuse to spend money on a
   sick machine, an ambiguous issue, or a dirty repo. When something is
   BLOCKED, read the reason: it usually ends with a question filed for a
   human to rule on, because the machine never rewrites meaning on its
   own.
3. **Everything you see is durable.** The console is just a view; the
   full record lands in `data/speedrun/runs/` and survives whether or not
   anyone watched. Press `v` to switch between terse and verbose at any
   time. Ctrl+C stops watching, never the roll.
