from proteus.core.rng import RNGManager, derive_repetition_seed


def _draw_uniforms(rng: RNGManager, stream_name: str, n: int) -> list[float]:
    stream = rng.stream(stream_name)
    return [stream.random() for _ in range(n)]


def test_same_seed_reproduces_identical_stream_sequences() -> None:
    a = RNGManager(base_seed=123)
    b = RNGManager(base_seed=123)

    assert _draw_uniforms(a, "latent", 5) == _draw_uniforms(b, "latent", 5)
    assert _draw_uniforms(a, "agents.mm-1", 5) == _draw_uniforms(b, "agents.mm-1", 5)
    assert _draw_uniforms(a, "latency", 5) == _draw_uniforms(b, "latency", 5)


def test_streams_are_isolated_across_subsystems() -> None:
    baseline = RNGManager(base_seed=7)
    baseline_latent = _draw_uniforms(baseline, "latent", 8)

    perturbed = RNGManager(base_seed=7)
    _ = _draw_uniforms(perturbed, "agents.mm-1", 100)
    perturbed_latent = _draw_uniforms(perturbed, "latent", 8)

    assert baseline_latent == perturbed_latent


def test_stream_returns_persistent_rng_instance() -> None:
    rng = RNGManager(base_seed=99)
    s1 = rng.stream("mechanism")
    s2 = rng.stream("mechanism")
    assert s1 is s2


def test_reset_replays_streams_identically() -> None:
    rng = RNGManager(base_seed=42)
    first = _draw_uniforms(rng, "metrics", 6)
    rng.reset()
    second = _draw_uniforms(rng, "metrics", 6)
    assert first == second


def test_derive_repetition_seed_is_deterministic_and_distinct() -> None:
    assert derive_repetition_seed(100, 0) == derive_repetition_seed(100, 0)
    assert derive_repetition_seed(100, 0) != derive_repetition_seed(100, 1)
