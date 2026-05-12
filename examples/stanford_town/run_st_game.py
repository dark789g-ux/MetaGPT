#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Desc   : entry of Stanford Town(ST/st) game
#           README see `metagpt/ext/stanford_town/README.md`

import asyncio
import json
from typing import Optional

import fire

from metagpt.ext.stanford_town.roles.st_role import STRole
from metagpt.ext.stanford_town.stanford_town import StanfordTown
from metagpt.ext.stanford_town.utils import llm_logger
from metagpt.ext.stanford_town.utils.const import STORAGE_PATH
from metagpt.ext.stanford_town.utils.mg_ga_transform import (
    get_reverie_meta,
    write_curr_sim_code,
    write_curr_step,
)
from metagpt.ext.stanford_town.utils.utils import copy_folder
from metagpt.logs import logger


async def startup(
    idea: str,
    fork_sim_code: str,
    sim_code: str,
    temp_storage_path: str,
    investment: float = 30.0,
    n_round: int = 500,
    personas: Optional[str] = None,
    inner_voice: Optional[str] = None,
):
    town = StanfordTown()
    logger.info("StanfordTown init environment")

    # copy `storage/{fork_sim_code}` to `storage/{sim_code}`
    copy_folder(str(STORAGE_PATH.joinpath(fork_sim_code)), str(STORAGE_PATH.joinpath(sim_code)))

    # Read the new sim's meta (a fresh copy of the fork base's) so we can edit
    # it in place if the caller asked for a persona subset.
    reverie_meta = get_reverie_meta(sim_code)

    if personas:
        selected = [p.strip() for p in personas.split(",") if p.strip()]
        unknown = set(selected) - set(reverie_meta["persona_names"])
        if unknown:
            raise SystemExit(f"unknown personas: {sorted(unknown)}")
        reverie_meta["persona_names"] = selected
        meta_path = STORAGE_PATH.joinpath(sim_code, "reverie", "meta.json")
        meta_path.write_text(json.dumps(reverie_meta, indent=2), encoding="utf-8")
        logger.info(f"persona subset applied: {selected}")

    iv = inner_voice or reverie_meta["persona_names"][0]
    if iv not in reverie_meta["persona_names"]:
        raise SystemExit(f"inner_voice '{iv}' not in personas {reverie_meta['persona_names']}")

    roles = []
    sim_path = STORAGE_PATH.joinpath(sim_code)
    sim_path.mkdir(exist_ok=True)
    for role_name in reverie_meta["persona_names"]:
        has_inner_voice = (role_name == iv)
        role = STRole(
            name=role_name,
            profile=role_name,
            sim_code=sim_code,
            step=reverie_meta.get("step", 0),
            start_time=reverie_meta.get("start_date"),
            curr_time=reverie_meta.get("curr_time"),
            sec_per_step=reverie_meta.get("sec_per_step"),
            has_inner_voice=has_inner_voice,
        )
        roles.append(role)

    # init temp_storage
    write_curr_sim_code({"sim_code": sim_code}, temp_storage_path)
    llm_logger.set_sim_code(sim_code)
    write_curr_step({"step": reverie_meta.get("step", 0)}, temp_storage_path)

    await town.hire(roles)

    town.invest(investment)
    town.run_project(idea)

    await town.run(n_round)


def main(
    idea: str,
    fork_sim_code: str,
    sim_code: str,
    temp_storage_path: Optional[str] = None,
    investment: float = 30.0,
    n_round: int = 500,
    personas: Optional[str] = None,
    inner_voice: Optional[str] = None,
):
    """
    Args:
        idea: idea works as an `inner voice` to the first agent.
        fork_sim_code: old simulation name to start with, choose one inside `generative_agents/environment/frontend_server/storage/`
        sim_code: new simulation name to save simulation result
        temp_storage_path: generative_agents temp_storage path inside `environment/frontend_server` to interact.
        investment: the investment of running agents
        n_round: rounds to run agents
        personas: optional comma-separated subset of the fork base's persona_names; when set, the new sim's meta.json is rewritten to this subset.
        inner_voice: optional persona name to receive the idea; must be in `personas` when both are given. Defaults to the first persona in meta.
    """

    asyncio.run(
        startup(
            idea=idea,
            fork_sim_code=fork_sim_code,
            sim_code=sim_code,
            temp_storage_path=temp_storage_path,
            investment=investment,
            n_round=n_round,
            personas=personas,
            inner_voice=inner_voice,
        )
    )


if __name__ == "__main__":
    fire.Fire(main)
