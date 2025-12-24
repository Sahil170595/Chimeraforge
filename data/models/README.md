---
license: apache-2.0
thumbnail: https://cdn-uploads.huggingface.co/production/uploads/6625f4a8a8d1362ebcc3851a/iyzgR89q50pp1T8HeeP15.png
base_model: ArliAI/gpt-oss-20b-Derestricted
pipeline_tag: text-generation
tags:
- abliterated
- derestricted
- gpt-oss-20b
- openai
- unlimited
- uncensored
- llama-cpp
- gguf-my-repo
library_name: transformers
---

# gghfez/gpt-oss-20b-Derestricted-Q4_K_M-GGUF
This model was converted to GGUF format from [`ArliAI/gpt-oss-20b-Derestricted`](https://huggingface.co/ArliAI/gpt-oss-20b-Derestricted) using llama.cpp via the ggml.ai's [GGUF-my-repo](https://huggingface.co/spaces/ggml-org/gguf-my-repo) space.
Refer to the [original model card](https://huggingface.co/ArliAI/gpt-oss-20b-Derestricted) for more details on the model.

## Use with llama.cpp
Install llama.cpp through brew (works on Mac and Linux)

```bash
brew install llama.cpp

```
Invoke the llama.cpp server or the CLI.

### CLI:
```bash
llama-cli --hf-repo gghfez/gpt-oss-20b-Derestricted-Q4_K_M-GGUF --hf-file gpt-oss-20b-derestricted-q4_k_m.gguf -p "The meaning to life and the universe is"
```

### Server:
```bash
llama-server --hf-repo gghfez/gpt-oss-20b-Derestricted-Q4_K_M-GGUF --hf-file gpt-oss-20b-derestricted-q4_k_m.gguf -c 2048
```

Note: You can also use this checkpoint directly through the [usage steps](https://github.com/ggerganov/llama.cpp?tab=readme-ov-file#usage) listed in the Llama.cpp repo as well.

Step 1: Clone llama.cpp from GitHub.
```
git clone https://github.com/ggerganov/llama.cpp
```

Step 2: Move into the llama.cpp folder and build it with `LLAMA_CURL=1` flag along with other hardware-specific flags (for ex: LLAMA_CUDA=1 for Nvidia GPUs on Linux).
```
cd llama.cpp && LLAMA_CURL=1 make
```

Step 3: Run inference through the main binary.
```
./llama-cli --hf-repo gghfez/gpt-oss-20b-Derestricted-Q4_K_M-GGUF --hf-file gpt-oss-20b-derestricted-q4_k_m.gguf -p "The meaning to life and the universe is"
```
or 
```
./llama-server --hf-repo gghfez/gpt-oss-20b-Derestricted-Q4_K_M-GGUF --hf-file gpt-oss-20b-derestricted-q4_k_m.gguf -c 2048
```
