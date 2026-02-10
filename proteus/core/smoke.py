"""Bootstrap smoke check for module wiring."""

from __future__ import annotations

from proteus.agents.informed import InformedTraderAgent
from proteus.agents.market_maker import MarketMakerAgent
from proteus.agents.noise import NoiseTraderAgent
from proteus.core.clock import EventClock
from proteus.core.rng import RNGManager
from proteus.execution.latency import ConstantLatencyModel
from proteus.execution.leakage import PublicTapeLeakagePolicy
from proteus.experiments.runner import build_mechanism
from proteus.experiments.scenarios import clob_smoke_scenario
from proteus.info.latent_process import StaticLatentProcess
from proteus.info.signal_model import IdentitySignalModel
from proteus.metrics.recorder import Recorder


def run_smoke_check() -> str:
    """Instantiate core modules and return a concise status string."""

    scenario = clob_smoke_scenario(seed=7)
    rng = RNGManager(base_seed=scenario.seed)
    clock = EventClock()
    mechanism = build_mechanism(scenario)
    latent = StaticLatentProcess(p0=0.5)
    signal = IdentitySignalModel()
    latency = ConstantLatencyModel()
    leakage = PublicTapeLeakagePolicy()
    recorder = Recorder()
    agents = [
        MarketMakerAgent("mm-1"),
        InformedTraderAgent("inf-1"),
        NoiseTraderAgent("noise-1"),
    ]

    _ = (
        rng.stream("smoke"),
        clock.now_ms,
        mechanism.name,
        latent.step(1),
        signal.observe("mm-1", 0, 0.5),
    )
    _ = (latency.submission_delay_ms(), leakage.is_visible)
    _ = (recorder.events, len(agents))

    return "smoke-ok"
