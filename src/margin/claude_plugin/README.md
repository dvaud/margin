# Margin for Claude Code

This plugin lets Claude Code, signed in with your own Claude plan, do the reading for Margin: profile labels, concept
links, theme names, references, search words and checks. Margin keeps your documents, results and reviews on your
computer and checks every quote; only the passages inside the tasks Claude Code takes are sent to Anthropic.

## Set it up (once)

1. In Margin: Settings, AI model service, choose **Claude Code (your subscription)** and confirm.
2. In a terminal: `margin claude-setup`. It prepares this plugin in your Margin folder, checks that the Margin
   connector starts, and prints two lines.
3. Type those two lines (they add the plugin to Claude Code):

   ```
   claude plugin marketplace add "<your Margin folder>/claude-plugin"
   claude plugin install margin-run@margin
   ```

   Inside Claude Code the same works as `/plugin marketplace add …` and `/plugin install margin-run@margin`.
4. Restart Claude Code. The first time it starts the Margin connector it may ask you to allow it.

## Use it

Press an AI button in Margin (Label with the AI, Ask the AI to relate them, Name the themes, Check…). The page says
what waits, for example *Waiting for Claude Code: 120 passages to label*. Then, in Claude Code, opened in any folder:

```
/margin-run Pilot              # every kind of task waiting in the project Pilot
/margin-run Pilot label        # only the labels
/margin-run Pilot --parallel 4 # four helpers at the same time (faster, uses your plan's limit faster)
/margin-run Pilot --helpers checker=2,labeller=1   # only these helpers, as many of each at the same time
```

Without `--parallel`, it goes at the speed chosen in the Margin app (Slower 1, Normal 2, Faster 4 helpers at once).

Each kind of task goes to a helper on the model Margin names for it: labels and links on Haiku, theme names,
references, search words and checks on Sonnet, second opinions on Opus. Unsure answers go once to a stronger model. You follow the
progress in the Margin app.

A run can stop at any moment (a usage limit, a closed laptop, Ctrl+C): a batch handed out and not answered returns to
the queue after 30 minutes, and the next `/margin-run` continues where it stopped.

## What it can do

The helpers can use only the Margin queue tools: they read nothing but the passages the queue hands them and write
nothing but answers. Margin never handles your login and never runs on anyone else's plan. When you press
*Start Claude Code* in the app, Margin starts Claude Code for you with only the Margin queue tools allowed.
