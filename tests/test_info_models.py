from __future__ import annotations

from proteus.info.latent_process import BoundedLogOddsLatentProcess, JumpConfig
from proteus.info.signal_model import AgentSignalConfig, HeterogeneousSignalModel


def test_latent_process_stays_bounded_with_noise_and_jumps() -> None:
    process = BoundedLogOddsLatentProcess(
        p0=0.35,
        phi=0.98,
        sigma_eta=0.8,
        jump=JumpConfig(intensity_per_second=5.0, mean=0.0, stddev=0.4),
    )

    for _ in range(1_000):
        p_t = process.step(delta_ms=10)
        assert 0.0 <= p_t <= 1.0


def test_latent_process_supports_toggle_configurations() -> None:
    deterministic = BoundedLogOddsLatentProcess(p0=0.42, phi=1.0, sigma_eta=0.0)
    deterministic.reset(seed=9)

    path = [deterministic.step(delta_ms=100) for _ in range(5)]
    assert path == [0.42, 0.42, 0.42, 0.42, 0.42]

    mean_reverting = BoundedLogOddsLatentProcess(p0=0.8, phi=0.9, sigma_eta=0.0, jump=JumpConfig())
    mean_reverting.reset(seed=1)
    p_start = mean_reverting.step(delta_ms=10)
    p_later = mean_reverting.step(delta_ms=10)
    assert p_later < p_start


def test_signal_model_delay_and_noise_heterogeneity() -> None:
    model = HeterogeneousSignalModel(
        default=AgentSignalConfig(delay_ms=0, noise_stddev=0.0),
        per_agent={
            "fast": AgentSignalConfig(delay_ms=0, noise_stddev=0.0),
            "slow": AgentSignalConfig(delay_ms=20, noise_stddev=0.0),
            "noisy": AgentSignalConfig(delay_ms=0, noise_stddev=0.2),
        },
    )
    model.reset(seed=77)

    truth = [
        (0, 0.10),
        (10, 0.30),
        (20, 0.90),
    ]

    fast_obs = [model.observe("fast", ts, p_t) for ts, p_t in truth]
    assert fast_obs == [0.10, 0.30, 0.90]

    model.reset(seed=77)
    slow_obs = [model.observe("slow", ts, p_t) for ts, p_t in truth]
    assert slow_obs == [0.10, 0.10, 0.10]

    model.reset(seed=77)
    noisy_obs = [model.observe("noisy", ts, p_t) for ts, p_t in truth]
    assert noisy_obs != [0.10, 0.30, 0.90]
    for obs in noisy_obs:
        assert 0.0 <= obs <= 1.0
