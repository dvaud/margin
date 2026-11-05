"""This installation's own add-on: the local layer's Python file (0.13.5). Margin ships it empty and its releases
never edit it.

A fork of Margin fills it in; Margin reads only the names defined here and keeps its own defaults for the rest. A
separate package does the same in a module of its own, named under the entry point `margin.extensions`. What each
name does, with an example, is in docs/EXTENDING.md; for instance:

    BRAND = {"name": "Margin", "tagline": "a writing companion"}
"""
