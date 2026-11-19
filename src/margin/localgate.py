"""The local gate of a job (0.19.13): the local model starts only when the person presses its own Start.

A job of the app may have work for two engines: Claude (Claude Code's queue, or the Claude API) and the local model on
this computer (the documents marked Only a local AI, and the AI mix's share). Before 0.19.13 the local model started by
itself inside such a job; now starting Claude and starting the local model are two separate clicks. Each job has a
`LocalGate`:

- ``wait``  the local part waits for its Start (the default of a job that also has work for Claude, and the state
            after a memory refusal: `memory.short`);
- ``go``    the local model may read (its Start was pressed, or the job is all local and was started by its own
            button);
- ``force`` as ``go``, whatever memory this computer has free ("Start it anyway").

A gate starts ``auto``, which waits like ``wait`` (0.20.1: also in a job whose only reader is the local model, such as
*Name the themes* when every theme may only be read on this computer: the button that asked for the work is not the
local model's own Start). A job started by that Start opens its gate at once (`Jobs.start(local_start="go")`); when the
local model is the main AI itself, no gate stands before it (`access.Readers.before_local`). Nothing loads the model
while the gate waits: every request of the local model passes `wait_open` first (`access.Readers` wraps the model), and
the features that have both kinds of work hand the local items to the gate's worker (`later`), which reads them as soon
as the gate opens, beside Claude, and goes back to waiting after the item in hand when the person presses Stop on the
local side (`close`). `drain` waits for the worker at the end of the job's own work.

The gate of the job a thread works for is `GATE` (a context variable the app's jobs set); outside a job (the command
line, the MCP connector) there is none, and the local model reads at once, as before: no person is there to press
Start.
"""
from __future__ import annotations

import contextvars
import threading
from collections import deque
from typing import Any, Callable

AUTO, WAIT, GO, FORCE = "auto", "wait", "go", "force"

GATE: contextvars.ContextVar["LocalGate | None"] = contextvars.ContextVar("margin_local_gate", default=None)


class LocalGate:
    POLL = 0.25  # seconds: how often a wait looks at the job's Stop

    def __init__(self, state: str = AUTO):
        self.state = state
        self.cond = threading.Condition()
        self.involved = False           # the job has work for the local model (its view then has "local")
        self.noun = "task"              # what waits: excerpt, passage, theme, pair, task, document
        self.counted = 0                # items waiting that the job counts itself (`involve(waiting=…)`)
        self.model: str | None = None
        self.memory: dict | None = None
        self.problem: str | None = None
        self.epoch = 0                  # how often the gate was opened (a refusal before the last opening is past)
        self.refusals = 0
        self.should_stop: Callable[[], bool] | None = None   # the job's Stop
        # (release, take, held) of the job's turn at the model (Jobs.model_lock): let go while the gate waits, so a job
        # that waits for the person never holds back the others, and taken back before the local model reads
        self.hold: tuple[Callable[[], bool], Callable[[], None], Callable[[], bool]] | None = None
        self.ended = False              # the job has ended: nothing more is read, nothing waits on
        self.report: Callable[[dict], Any] | None = None     # how the local model reports to the job's page
        self._looked = False
        self._items: deque = deque()
        self._worker: threading.Thread | None = None
        self._error: BaseException | None = None
        self._stop: Callable[[], bool] | None = None   # a feature's own Stop, given to `drain`
        # 0.19.15: the local model's requests in hand now, and the models asked ((address, model)): Stop on the local
        # side lets go of their memory once nothing is in hand (`put_down`), not after Ollama's 15 minutes
        self.in_hand = 0
        self.asked: set[tuple[str, str]] = set()

    # -- state ----------------------------------------------------------------------------------------------------
    @property
    def is_open(self) -> bool:
        return self.state in (GO, FORCE)

    @property
    def public(self) -> str:
        return WAIT if self.state == AUTO else self.state

    @property
    def waiting(self) -> int:
        with self.cond:
            return self.counted + sum(n for _fn, n in self._items)

    def stopped(self, extra: Callable[[], bool] | None = None) -> bool:
        if self.ended:
            return True
        for f in (extra, self.should_stop):
            try:
                if f is not None and f():
                    return True
            except Exception:  # noqa: BLE001 - a broken Stop never keeps the gate shut for good
                pass
        return False

    def mixed(self) -> None:
        """The job has work for Claude too: its local part waits for its own Start (unless it was pressed)."""
        with self.cond:
            if self.state == AUTO:
                self.state = WAIT

    def open(self, force: bool = False) -> None:
        """The person pressed Start (`force`: Start it anyway, whatever memory is free)."""
        with self.cond:
            self.state = FORCE if force else GO
            self.epoch += 1
            if force and self.memory:
                self.memory = {**self.memory, "short": False}
            self.cond.notify_all()

    def close(self) -> None:
        """Stop on the local side: back to waiting after the item in hand (the job's own Stop ends everything). 0.19.15:
        the local model lets go of its memory as soon as nothing is in hand."""
        with self.cond:
            if self.is_open:
                self.state = WAIT
            if not self.in_hand:
                self._let_go()
            self.cond.notify_all()

    def hand(self, url: str | None, model: str | None) -> None:
        """0.19.15: a request of the local model begins (`access._Gated`)."""
        with self.cond:
            self.in_hand += 1
            if url and model:
                self.asked.add((url.rstrip("/"), model))

    def put_down(self) -> None:
        """0.19.15: a request of the local model has ended: after Stop on the local side, the model lets go of its
        memory now that nothing is in hand."""
        with self.cond:
            self.in_hand = max(0, self.in_hand - 1)
            if not self.in_hand and not self.is_open and not self.ended:
                self._let_go()

    def _let_go(self) -> None:
        """Free the memory of the local models this job asked (in a thread of its own: one short request to Ollama).
        Called with `cond` held."""
        if not self.asked:
            return
        from .llm import let_go

        models, self.asked = set(self.asked), set()
        threading.Thread(target=let_go, args=(models,), daemon=True, name="local-let-go").start()

    def refused(self, e) -> None:
        """The local model was not started: too little memory free (`llm.MemoryShort`). It waits again, with the
        numbers, for Start (or Start it anyway)."""
        with self.cond:
            self.state = WAIT
            self.refusals += 1
            self.involved = True
            if hasattr(e, "need"):
                self.memory = {"need": int(e.need), "free": int(e.free), "short": True}
            self.model = getattr(e, "model", None) or self.model
            self.cond.notify_all()

    def involve(self, waiting: int | None = None, noun: str | None = None, look: Callable[[], dict] | None = None,
                report: Callable[[dict], Any] | None = None, problem: str | None = None) -> None:
        """The job has work for the local model: `waiting` items (counted by the job itself), what they are, how to
        learn the model's name and memory (`look`, asked once, without starting it) and how to report to the page."""
        with self.cond:
            self.involved = True
            if noun:
                self.noun = noun
            if waiting is not None:
                self.counted = max(0, int(waiting))
            if report is not None:
                self.report = report
            if problem:
                self.problem = problem
            first = not self._looked and look is not None
            if first:
                self._looked = True
        if first:
            try:
                got = look() or {}
            except Exception:  # noqa: BLE001 - what the panel shows never stops the work
                got = {}
            with self.cond:
                self.model = got.get("model") or self.model
                self.memory = self.memory or got.get("memory")
                self.problem = self.problem or got.get("problem")

    def view(self) -> dict | None:
        """`job.local` of the job's view (None: no work for the local model)."""
        if not self.involved:
            return None
        return {"gate": self.public, "waiting": self.waiting, "noun": self.noun, "model": self.model,
                "memory": dict(self.memory) if self.memory else None, "problem": self.problem}

    # -- waiting --------------------------------------------------------------------------------------------------
    def say_ready(self) -> None:
        """progress.model = {"who": "local", "phase": "ready"}: the local model waits for its Start."""
        if self.report is None:
            return
        try:
            self.report({"who": "local", "phase": "ready", "model": self.model})
        except Exception:  # noqa: BLE001 - a display problem must never stop the work
            pass

    def _release(self) -> bool:
        if self.hold is None:
            return False
        try:
            return bool(self.hold[0]())
        except Exception:  # noqa: BLE001
            return False

    def _take(self) -> None:
        if self.hold is not None:
            self.hold[1]()

    def _has_turn(self) -> bool:
        """Whether the job holds its turn at the model now (always, for a job that does not take turns)."""
        if self.hold is None:
            return True
        try:
            return bool(self.hold[2]())
        except Exception:  # noqa: BLE001
            return True

    def end(self) -> None:
        """The job has ended (done, failed or stopped): the worker reads nothing more and stops waiting."""
        with self.cond:
            self.ended = True
            self.cond.notify_all()

    def wait_open(self, should_stop: Callable[[], bool] | None = None) -> bool:
        """Wait until the local model may read. True: it may; False: the job was stopped meanwhile. 0.20.1: a gate
        still ``auto`` waits too (before, it opened when no feature had said the job has work for Claude, so the
        button that asked for the work started the local model)."""
        with self.cond:
            if self.state == AUTO:
                self.state = WAIT
            if self.is_open:
                return True
            assumed = not self.waiting
            if assumed:   # its Start is offered only while something waits: a request that nobody counted is one
                self.counted = 1
        self.say_ready()
        released = self._release()
        try:
            with self.cond:
                while not self.is_open:
                    if self.stopped(should_stop):
                        return False
                    self.cond.wait(self.POLL)
                if assumed and self.counted == 1:
                    self.counted = 0
            return True
        finally:
            if released:
                self._take()

    # -- the worker: local items beside Claude's ----------------------------------------------------------------------
    def later(self, fn: Callable[[], Any], n: int = 1, noun: str | None = None, mixed: bool = True, ws=None) -> None:
        """Read one item with the local model as soon as the gate opens (at once when it is open), in the gate's
        worker, beside the job's own thread. `n`: how many things it counts as waiting (excerpts of a part, say).
        `mixed`: the job has work for Claude too (0.20.1: every gate waits for its Start; kept to say so). An item the model was refused for
        (memory) waits for the next opening and is read again; it must be safe to run again."""
        from . import tasks

        if mixed:
            self.mixed()
        with self.cond:
            self.involved = True
            if noun:
                self.noun = noun
            self._items.append((fn, max(0, int(n))))
            if self._worker is None and self._error is None:
                ctx = contextvars.copy_context()
                self._worker = threading.Thread(target=ctx.run, args=(self._work, tasks.queue_mode(), ws),
                                                daemon=True, name="local-gate")
                self._worker.start()

    def _work(self, queued: bool, ws) -> None:
        from . import tasks
        from .llm import MemoryShort

        try:
            with tasks.queueing(queued):
                while True:
                    with self.cond:
                        if not self._items or self.ended:
                            self._worker = None   # in the same step: an item handed over now starts a new worker
                            self.cond.notify_all()
                            return
                        fn, _n = self._items[0]
                    if not self.wait_open(self._stop):
                        return  # the job was stopped: what is left waits for the local model, as before
                    with self.cond:  # the job's turn at the model first (taken back by `drain` once the gate opens)
                        while not self._has_turn() and self.is_open:
                            if self.stopped(self._stop):
                                return
                            self.cond.wait(self.POLL)
                        if not self.is_open:
                            continue  # Stop on the local side meanwhile: wait for Start again
                    before = self.refusals
                    try:
                        fn()
                    except MemoryShort as e:
                        if self.refusals == before:
                            self.refused(e)
                    except BaseException as e:  # noqa: BLE001 - handed to the job's thread (drain)
                        with self.cond:
                            self._error = e
                            self._items.clear()
                        return
                    with self.cond:
                        if self.refusals == before:
                            self._items.popleft()
                        self.cond.notify_all()
        finally:
            with self.cond:
                if self._worker is threading.current_thread():
                    self._worker = None
                self.cond.notify_all()
            if ws is not None:
                try:
                    ws.close()
                except Exception:  # noqa: BLE001
                    pass

    def busy(self) -> bool:
        with self.cond:
            return self._worker is not None

    def drain(self, should_stop: Callable[[], bool] | None = None) -> None:
        """Wait until the worker has read every item (or, the job stopped, has put down the one in hand). The job's
        turn at the model is let go while the gate waits. An error of an item is raised here, in the job's thread."""
        released = False
        if should_stop is not None:
            self._stop = should_stop
        try:
            while True:
                with self.cond:
                    if self._worker is None:
                        break
                    is_open = self.is_open
                if not is_open and not released:
                    released = self._release()
                elif is_open and released:
                    self._take()   # the local model reads now: with the job's turn at the model
                    released = False
                    with self.cond:
                        self.cond.notify_all()
                with self.cond:
                    if self._worker is not None:
                        self.cond.wait(self.POLL)
        finally:
            if released:
                self._take()
        with self.cond:
            err, self._error = self._error, None
        if err is not None:
            raise err
