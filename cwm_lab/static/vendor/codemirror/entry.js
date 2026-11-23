// Point d'entrée du bundle CodeMirror 6 pour l'outil TP (lab/lab_web).
// Ré-exporte l'API publique utilisée par lab/lab_web/static/app.js.
import { EditorState, EditorSelection } from "@codemirror/state";
import { EditorView, keymap, Decoration } from "@codemirror/view";
import { syntaxHighlighting, HighlightStyle, indentUnit } from "@codemirror/language";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { searchKeymap, highlightSelectionMatches } from "@codemirror/search";
import { closeBrackets, autocompletion } from "@codemirror/autocomplete";
import { linter, lintGutter, forceLinting } from "@codemirror/lint";
import { tags } from "@lezer/highlight";
import { turtle } from "codemirror-lang-turtle";
import { basicSetup } from "codemirror";

export {
  EditorState, EditorSelection, EditorView, keymap, Decoration,
  syntaxHighlighting, HighlightStyle, indentUnit,
  defaultKeymap, history, historyKeymap,
  searchKeymap, highlightSelectionMatches,
  closeBrackets, autocompletion,
  linter, lintGutter, forceLinting,
  tags, turtle, basicSetup,
};
