# TR115 Runtime Comparison

## Summary

| Runtime | Peak Eff | Mean Eff | Gain vs TR114 | Gap vs TR110 | StdDev |
|---------|----------|----------|---------------|--------------|--------|
| tokio-default | 92.9% | 90.0% | +-2.8pp | -6.3pp | 3.9pp |
| tokio-localset | 93.6% | 88.4% | +-2.1pp | -5.7pp | 3.7pp |
| async-std | 50.0% | 50.0% | +-45.7pp | -49.3pp | 0.0pp |
| smol | 92.4% | 90.5% | +-3.3pp | -6.9pp | 1.8pp |
| smol-1kb | 92.5% | 88.8% | +-3.2pp | -6.7pp | 3.7pp |

## Baseline References

- TR114 baseline (tokio-default): 95.7%
- TR110 target (Python dual Ollama): 99.25%
