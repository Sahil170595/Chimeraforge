# Contributing to Chimeraforge

Thank you for your interest in contributing to Chimeraforge! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment. We are committed to providing a harassment-free experience for everyone.

## Getting Started

### Prerequisites

- Python 3.11+
- Rust 1.70+ (for Rust contributions)
- Git
- Familiarity with the project structure (see [ARCHITECTURE.md](docs/ARCHITECTURE.md))

### Development Setup

1. **Fork and Clone**:
   ```bash
   git clone https://github.com/your-org/Chimeraforge.git
   cd Chimeraforge
   ```

2. **Set Up Python Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set Up Rust Environment** (if contributing Rust code):
   ```bash
   cd src/rust/demo_agent && cargo build
   cd ../demo_multiagent && cargo build
   cd ../../..
   ```

## Contribution Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Changes

- Follow the existing code style
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

### 3. Commit Changes

Use clear, descriptive commit messages:

```bash
git commit -m "Add feature: description of what was added"
git commit -m "Fix bug: description of what was fixed"
```

### 4. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear description of changes
- Reference to related issues
- Screenshots/evidence if applicable

## Coding Standards

### Python

- **Style**: Follow PEP 8
- **Type Hints**: Use type hints for function signatures
- **Docstrings**: Use Google-style docstrings
- **Formatting**: Use `black` for formatting
- **Linting**: Use `flake8` for linting

Example:
```python
def benchmark_agent(
    agent: BaseAgent,
    runs: int = 5,
    model: str = "gemma3:latest"
) -> Dict[str, Any]:
    """
    Run benchmark for an agent.

    Args:
        agent: Agent instance to benchmark
        runs: Number of runs to execute
        model: Model name to use

    Returns:
        Dictionary containing benchmark results
    """
    ...
```

### Rust

- **Style**: Follow Rust style guide
- **Documentation**: Use `///` for public items
- **Formatting**: Use `rustfmt`
- **Linting**: Use `clippy`

Example:
```rust
/// Run benchmark for an agent.
///
/// # Arguments
///
/// * `agent` - Agent instance to benchmark
/// * `runs` - Number of runs to execute
/// * `model` - Model name to use
///
/// # Returns
///
/// Dictionary containing benchmark results
pub async fn benchmark_agent(
    agent: &dyn Agent,
    runs: usize,
    model: &str,
) -> Result<BenchmarkResults> {
    ...
}
```

## Documentation

### Code Documentation

- Document all public functions and classes
- Include examples in docstrings where helpful
- Keep documentation up to date with code changes

### User Documentation

- Update relevant documentation in `docs/`
- Add examples for new features
- Update README if needed
- Keep technical reports updated

## Testing

### Python Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agent.py

# Run with coverage
pytest --cov=banterhearts tests/
```

### Rust Tests

```bash
# Run all tests
cargo test

# Run specific test
cargo test test_benchmark_agent

# Run with output
cargo test -- --nocapture
```

## Benchmarking

### Adding New Benchmarks

1. Create benchmark script in appropriate location
2. Follow existing benchmark structure
3. Document methodology
4. Add to benchmark suite
5. Update documentation

### Running Benchmarks

```bash
# Python single-agent
python src/python/banterhearts/demo_agent/run_demo.py --runs 3

# Rust single-agent
cd src/rust/demo_agent && cargo run --release -- --runs 3

# Multi-agent (requires dual Ollama setup)
# See docs/dual_ollama_setup.md
```

## Pull Request Guidelines

### Before Submitting

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] Documentation updated
- [ ] No merge conflicts
- [ ] Commit messages are clear

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Refactoring

## Testing
How was this tested?

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

## Review Process

1. **Automated Checks**: CI/CD runs tests and linting
2. **Code Review**: At least one maintainer reviews
3. **Feedback**: Address any feedback
4. **Approval**: Once approved, PR is merged

## Areas for Contribution

### High Priority

- Performance optimizations
- Bug fixes
- Documentation improvements
- Test coverage improvements

### Medium Priority

- New agent implementations
- Additional metrics
- Analysis tools
- Visualization improvements

### Low Priority

- Code refactoring
- Style improvements
- Documentation formatting

## Questions?

- **Documentation**: Check `docs/` directory
- **Issues**: Open an issue on GitHub
- **Discussions**: Use GitHub Discussions
- **Email**: Contact maintainers directly

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to Chimeraforge!

