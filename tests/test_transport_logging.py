"""Native factory chaining and context isolation without global logging switches."""

from __future__ import annotations

import asyncio
import logging

import pytest

from chimeraforge.transport_logging import sdk_logging


def test_future_sdk_children_are_sanitized_before_existing_factory(monkeypatch):
    previous = logging.getLogRecordFactory()
    seen = []

    def custom(*args, **kwargs):
        seen.append((args, kwargs))
        record = previous(*args, **kwargs)
        record.caller_copy = repr((args[4:], kwargs))
        return record

    logger = logging.getLogger("httpcore.future.native.child")
    monkeypatch.setattr(logger, "level", logging.DEBUG)
    logging.setLogRecordFactory(custom)
    try:
        with sdk_logging(True):
            try:
                raise ValueError("FictionalException82")
            except ValueError:
                logger.error(
                    "FictionalMessage82 %s", "FictionalArgument82", exc_info=True, stack_info=True
                )
        assert len(seen) == 1
        assert all(
            value not in repr(seen)
            for value in ("FictionalException82", "FictionalMessage82", "FictionalArgument82")
        )
        assert logging.getLogRecordFactory() is custom
    finally:
        logging.setLogRecordFactory(previous)


def test_nested_anonymous_scope_and_other_loggers_keep_exact_records(monkeypatch):
    previous = logging.getLogRecordFactory()
    seen = []

    def custom(*args, **kwargs):
        seen.append((args[0], args[4], args[5]))
        return previous(*args, **kwargs)

    sdk, product = logging.getLogger("httpx.new.child"), logging.getLogger("chimeraforge.progress")
    for logger in (sdk, product):
        monkeypatch.setattr(logger, "level", logging.INFO)
    logging.setLogRecordFactory(custom)
    try:
        with sdk_logging(True):
            sdk.info("FictionalSecret82")
            with sdk_logging(False):
                sdk.info("anonymous %s", "unchanged")
            product.info("progress %s", 7)
            sdk.info("FictionalSecret82")
        assert seen == [
            (sdk.name, "secure transport event", ()),
            (sdk.name, "anonymous %s", ("unchanged",)),
            (product.name, "progress %s", (7,)),
            (sdk.name, "secure transport event", ()),
        ]
        assert logging.getLogRecordFactory() is custom
    finally:
        logging.setLogRecordFactory(previous)


@pytest.mark.asyncio
async def test_overlapping_secure_and_anonymous_owners_restore_only_last_slot(monkeypatch):
    previous = logging.getLogRecordFactory()
    seen = []
    entered, release = asyncio.Event(), asyncio.Event()
    logger = logging.getLogger("httpcore.concurrent")
    monkeypatch.setattr(logger, "level", logging.INFO)

    def custom(*args, **kwargs):
        seen.append((args[4], args[5]))
        return previous(*args, **kwargs)

    async def held():
        with sdk_logging(True):
            entered.set()
            await release.wait()
            logger.info("FictionalConcurrent82")

    logging.setLogRecordFactory(custom)
    owner = asyncio.create_task(held())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        with sdk_logging(True):
            logger.info("FictionalConcurrent82")
        assert logging.getLogRecordFactory() is not custom
        with sdk_logging(False):
            logger.info("anonymous concurrent %s", 3)
        release.set()
        await owner
        assert seen == [
            ("secure transport event", ()),
            ("anonymous concurrent %s", (3,)),
            ("secure transport event", ()),
        ]
        assert logging.getLogRecordFactory() is custom
    finally:
        release.set()
        await asyncio.gather(owner, return_exceptions=True)
        logging.setLogRecordFactory(previous)


def test_caller_chaining_an_older_wrapper_does_not_recurse_or_get_overwritten(monkeypatch):
    previous = logging.getLogRecordFactory()
    seen = []
    logger = logging.getLogger("httpx.future")
    monkeypatch.setattr(logger, "level", logging.INFO)
    try:
        with sdk_logging(True):
            older = logging.getLogRecordFactory()

            def caller(*args, **kwargs):
                seen.append((args[4], args[5]))
                return older(*args, **kwargs)

            logging.setLogRecordFactory(caller)
        assert logging.getLogRecordFactory() is caller
        with sdk_logging(True):
            logger.info("FictionalChained82 %s", "secret")
        assert seen == [("secure transport event", ())]
        assert logging.getLogRecordFactory() is caller
        logger.info("anonymous remains %s", "original")
        assert seen[-1] == ("anonymous remains %s", ("original",))
    finally:
        logging.setLogRecordFactory(previous)
