"use client";

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from "react";
import { splitUncertain } from "@/lib/notes";

export interface EditorHandle {
  /** Current text, without any highlighting. */
  getText: () => string;
}

/**
 * A plain-text editor that highlights words the OCR was unsure about. The highlight on a word
 * disappears as soon as the person edits it, so what is left is what still needs checking.
 * The text is built with DOM nodes (never innerHTML), so note text can't inject markup.
 */
export const HighlightEditor = forwardRef<EditorHandle, { initialText: string; onRemainingChange?: (n: number) => void }>(
  function HighlightEditor({ initialText, onRemainingChange }, ref) {
    const box = useRef<HTMLDivElement>(null);

    const count = useCallback(() => {
      onRemainingChange?.(box.current?.querySelectorAll("mark[data-uncertain]").length ?? 0);
    }, [onRemainingChange]);

    useEffect(() => {
      const el = box.current;
      if (!el) return;
      el.replaceChildren(
        ...splitUncertain(initialText).map((part) => {
          if (!part.uncertain) return document.createTextNode(part.text);
          const mark = document.createElement("mark");
          mark.dataset.uncertain = "true";
          mark.textContent = part.text;
          return mark;
        }),
      );
      count();
    }, [initialText, count]);

    useImperativeHandle(ref, () => ({
      getText: () => (box.current?.innerText ?? "").replace(/ /g, " "),
    }));

    function clearHighlightUnderCursor() {
      const anchor = window.getSelection()?.anchorNode;
      const mark = (anchor instanceof Element ? anchor : anchor?.parentElement)?.closest("mark[data-uncertain]");
      if (mark) delete (mark as HTMLElement).dataset.uncertain; // keeps the caret where it is
      count();
    }

    return (
      <div
        ref={box}
        contentEditable="plaintext-only"
        suppressContentEditableWarning
        role="textbox"
        aria-multiline="true"
        aria-label="Note text"
        spellCheck
        onInput={clearHighlightUnderCursor}
        className="min-h-[22rem] whitespace-pre-wrap rounded-lg border border-slate-300 bg-white p-4 text-[15px] leading-7 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200 [&_mark]:rounded [&_mark]:bg-amber-200 [&_mark]:px-0.5 [&_mark]:text-slate-900 [&_mark:not([data-uncertain])]:bg-transparent [&_mark:not([data-uncertain])]:px-0"
      />
    );
  },
);
