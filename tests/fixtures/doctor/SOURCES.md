# doctor fixtures

Every file here is real tool output, captured verbatim. None is hand-written. Tests that need a shape no capture shows (for example a banner in front of the JSON) build it around a real capture, and say so in the test.

Tiers: **local** = captured on the dev machine. **primary** = the vendor's own docs or blog. **vendor repo** = real output posted in the vendor's own GitHub repo. **third-party** = another project's test fixture or issue.

| File | Command | Source | Tier / license | Captured |
|---|---|---|---|---|
| nvidia_smi_query.csv | `nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader,nounits` | RTX 4080 Laptop, driver 616.92, Windows 11 | local | 2026-09-26 |
| nvidia_smi_header.txt | `nvidia-smi`, first 4 lines. This driver prints "CUDA UMD Version". | same machine | local | 2026-09-26 |
| windows_cim_registry.json | `doctor.WINDOWS_PROBE` via `powershell -NoProfile -NonInteractive -Command` | same machine (RTX 4080 Laptop + Intel UHD) | local | 2026-09-26 |
| amd_smi_static_mi300x_rocm721.json | `amd-smi static --json`, root, AMDSMI Tool 26.2.2, ROCm 7.2.1, 8x MI300X | https://github.com/huggingface/dell-ai/blob/eead83fd703f/tests/unit/system_info/resources/amd_smi_static_json_root.json | third-party, Apache-2.0 (Copyright Hugging Face / Dell; reproduced unmodified) | 2026-09-26 |
| amd_smi_version_rocm721.json | `amd-smi version --json`, root | https://github.com/huggingface/dell-ai/blob/eead83fd703f/tests/unit/system_info/resources/amd_smi_version_root.json | third-party, Apache-2.0 | 2026-09-26 |
| amd_smi_version_nonroot_rocm721.json | `amd-smi version --json`, no render-group access | https://github.com/huggingface/dell-ai/blob/eead83fd703f/tests/unit/system_info/resources/amd_smi_version_non_root.json | third-party, Apache-2.0 | 2026-09-26 |
| amd_smi_vram_fragment_rocm_blog.json | `amd-smi static --json \| jq '.[0]["vram"]'`. The `.[0]` shows the pre-ROCm-7.0 list shape. | https://github.com/ROCm/rocm-blogs/blob/25798803e1b6/blogs/software-tools-optimization/amd-smi-overview/README.md | primary (AMD) | 2026-09-26 |
| rocm_smi_meminfo_vram.json | `rocm-smi --showmeminfo vram --json`, raw one-line form | https://github.com/containers/ramalama/issues/239#issuecomment-2395602829 | third-party issue (MIT repo) | 2026-09-26 |
| rocm_smi_productname.json | `rocm-smi ... --showproductname --json`, pretty-printed by the poster | https://github.com/ROCm/rocm_smi_lib/issues/159 | vendor repo | 2026-09-26 |
| system_profiler_hardware_m2.json | `system_profiler SPHardwareDataType SPSoftwareDataType -json`, MacBook Air M2, macOS 14.4 | https://github.com/viktor-shcherb/hologram-reconstruction-using-physics-consistency/blob/4158de4b59ec/hardware_information.json | third-party, MIT. **Redacted:** serial_number, platform_UUID, provisioning_UDID, model_number, user_name and local_host_name replaced with "REDACTED". No parsed field touched. | 2026-09-26 |
| xpu_smi_discovery_dump_bmg.json | `xpu-smi discovery -j --dump 2`, which emitted per-device detail (4x Intel BMG 0xe211) | https://github.com/intel/xpumanager/issues/127 | vendor repo | 2026-09-26 |
| xpu_smi_discovery_list.json | `xpu-smi discovery -j` (summary list, no memory) | https://github.com/intel/xpumanager/blob/v1.3.8/doc/smi_user_guide.md | primary (Intel) | 2026-09-26 |
| wsl_osrelease.txt | `/proc/sys/kernel/osrelease` on WSL2 | https://github.com/microsoft/WSL/issues/423#issuecomment-611086412 (Microsoft staff) | vendor repo | 2026-09-26 |

Deliberately not vendored:
- **A real macOS `SPDisplaysDataType` capture:** AGPL-3.0, incompatible with this MIT package.
- **amd-smi non-root output:** non-ASCII.
- **A `sysctl` quote:** annotated by its reporter, not raw output.

Not found anywhere in real output:
- a consumer-Radeon `amd-smi static --json`;
- a rocm-smi driver-version JSON;
- an Apple-published Apple Silicon sample.
