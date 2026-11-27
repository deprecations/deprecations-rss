> ## Documentation Index
> Fetch the complete documentation index at: https://docs.fireworks.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Changelog

> Fireworks documentation changelog: recent additions, updates, and clarifications across serverless, fine-tuning, deployments, integrations, and API reference.

All

**2026-10-19**

Inference

# Upcoming Serverless deprecation: GPT OSS 120B, Inkling, Nemotron, and US endpoints for MiniMax M3 and GLM 5.3 Flash

Several Serverless models will be decommissioned on **November 7, 2026** to better serve newer, higher-performance replacements. This applies **only to serverless inference**. **Dedicated deployments and Reserved Throughput are unaffected.**

## **Action required**

If you use any of the models below on serverless, migrate to a recommended replacement **before November 7, 2026**. After that date, they will no longer be available via serverless endpoints.

## **Recommended migrations**

* **[GPT OSS 120B](https://app.fireworks.ai/models/fireworks/gpt-oss-120b)** — move to a dedicated deployment of **GPT OSS 120B**
* **Inkling** — migrate to **Muse Spark Open** (US endpoint, 50% US regional premium waived)
* **[NVIDIA Nemotron 3 Ultra](https://app.fireworks.ai/models/fireworks/nemotron-3-ultra-nvfp4)** — move to a dedicated deployment of **Nemotron Super VL**
* **[NVIDIA Nemotron 3.5 Lightning 30B A3B](https://app.fireworks.ai/models/fireworks/nemotron-lightning-3p5-30b-a3b)** — move to a dedicated deployment of **Nemotron Super VL**
* **[MiniMax M3](https://app.fireworks.ai/models/fireworks/minimax-m3) (US endpoint only)** — migrate to **DeepSeek V4.1 Flash 1017 (US endpoint)**. The global MiniMax M3 endpoint remains available.
* **[GLM 5.3 Flash](https://app.fireworks.ai/models/fireworks/glm-5p3-flash) (US endpoint only)** — migrate to **DeepSeek V4.1 Flash 1017 (US endpoint)**. The global GLM 5.3 Flash endpoint remains available.

[GLM 5.3](https://app.fireworks.ai/models/fireworks/glm-5p3) and [DeepSeek V4.1 Flash](https://app.fireworks.ai/models/fireworks/deepseek-v4p1-flash) are not affected and remain available on serverless.

## **New models on Serverless**

* **DeepSeek V4.1 Flash 1017:** `accounts/fireworks/models/deepseek-v4p1-flash-1017`
* **DeepSeek V4.1 Flash 1017 (US endpoint):** `accounts/fireworks/routers/deepseek-v4p1-flash-1017-us` ([US-only Serverless](https://docs.fireworks.ai/serverless/us-only-serverless.md))
* **Muse Spark Open** (US endpoint, 50% US regional premium waived): `accounts/fireworks/models/muse-spark-open`
* **MiniMax M3.1:** coming to serverless after its open-source release, expected Friday, October 23

If you want to switch to a dedicated deployment, see the [Serverless model list](https://fireworks.ai/models?modelTypes=Serverless) and the [on-demand deployment quickstart](https://docs.fireworks.ai/getting-started/ondemand-quickstart.md).

**2026-10-18**

Training

# Upcoming Serverless Training deprecation: DeepSeek V4 Flash (0731)

On **November 2, 2026**, **[DeepSeek V4 Flash (0731)](https://app.fireworks.ai/models/fireworks/deepseek-v4-flash-0731)** will be removed from the shared Serverless Training pool. This change applies only to Serverless Training.

If you train DeepSeek V4 Flash (0731) on Serverless Training, migrate to **[DeepSeek V4.1 Flash 1017](https://app.fireworks.ai/models/fireworks/deepseek-v4p1-flash-1017)** before November 2, 2026.

**2026-09-26**

Inference

# Serverless deprecation: DeepSeek V4 Pro (0813), DeepSeek V4 Flash (0731), and related models

The serverless deprecation announced for **September 25, 2026** is now in effect. The models below are no longer available on public serverless, including Fast and US-only serverless endpoints where those existed. Dedicated deployments are unaffected.

## **Recommended migrations**

* **[DeepSeek V4 Pro (0813)](https://app.fireworks.ai/models/fireworks/deepseek-v4-pro-0813)** — migrate to **[DeepSeek V4.1 Flash](https://app.fireworks.ai/models/fireworks/deepseek-v4p1-flash)**
* **[DeepSeek V4 Flash (0731)](https://app.fireworks.ai/models/fireworks/deepseek-v4-flash-0731)** — migrate to **[DeepSeek V4.1 Flash](https://app.fireworks.ai/models/fireworks/deepseek-v4p1-flash)**
* **[DeepSeek V4 Flash Vision Exp](https://app.fireworks.ai/models/fireworks/deepseek-v4-flash-vision-exp)** — migrate to **[DeepSeek V4.1 Flash](https://app.fireworks.ai/models/fireworks/deepseek-v4p1-flash)**
* **[Muse Glimmer 30B](https://app.fireworks.ai/models/fireworks/muse-glimmer-30b)** — migrate to **[NVIDIA Nemotron 3.5 Lightning 30B A3B](https://app.fireworks.ai/models/fireworks/nemotron-lightning-3p5-30b-a3b)**
* **[Kimi K2.6](https://app.fireworks.ai/models/fireworks/kimi-k2p6)** — migrate to **[GLM 5.3](https://app.fireworks.ai/models/fireworks/glm-5p3)** or **[Kimi K3](https://app.fireworks.ai/models/fireworks/kimi-k3)**
* **[Kimi K2.7 Code](https://app.fireworks.ai/models/fireworks/kimi-k2p7-code)** — migrate to **[GLM 5.3](https://app.fireworks.ai/models/fireworks/glm-5p3)** or **[Kimi K3](https://app.fireworks.ai/models/fireworks/kimi-k3)**
* **[GLM 5.2](https://app.fireworks.ai/models/fireworks/glm-5p2)**, including **GLM 5.2 Fast**, **GLM 5.2 Fast US**, and **GLM 5.2 US** — migrate to **[GLM 5.3](https://app.fireworks.ai/models/fireworks/glm-5p3)**

See [Serverless pricing](https://docs.fireworks.ai/serverless/pricing.md) and [Which model should I use?](https://docs.fireworks.ai/guides/recommended-models.md).

**2026-09-22**

Training

# New Serverless Training model: GLM 5.3 Flash

**[GLM 5.3 Flash](https://app.fireworks.ai/models/fireworks/glm-5p3-flash)** is now available for LoRA workloads on the shared Serverless Training pool, with up to 200K context and both text and vision inputs.

See the [Serverless Training guide](https://docs.fireworks.ai/fine-tuning/training-api/serverless.md) for setup and the [training model catalog](https://docs.fireworks.ai/fine-tuning/models.md) for current availability.

**2026-09-12**

Inference

# Upcoming Serverless deprecation: older DeepSeek, GLM, Muse, and Kimi models

Several older Serverless models will be decommissioned on **September 25, 2026** to better serve newer, higher-performance replacements. This applies **only to serverless endpoints**, including Fast and US-only Serverless endpoints for models that have those variants. **Dedicated deployments are unaffected.**

## **Action required**

If you use any of the models below on serverless, migrate to a recommended replacement **before September 25, 2026**. After that date, they will no longer be available via serverless endpoints.

## **Recommended migrations**

* **[DeepSeek V4 Flash (0731)](https://app.fireworks.ai/models/fireworks/deepseek-v4-flash-0731)** — migrate to **[DeepSeek V4.1 Flash](https://app.fireworks.ai/models/fireworks/deepseek-v4p1-flash)**
* **[DeepSeek V4 Pro (0813)](https://app.fireworks.ai/models/fireworks/deepseek-v4-pro-0813)** — migrate to **[DeepSeek V4.1 Flash](https://app.fireworks.ai/models/fireworks/deepseek-v4p1-flash)**
* **[DeepSeek V4 Flash Vision Exp](https://app.fireworks.ai/models/fireworks/deepseek-v4-flash-vision-exp)** — migrate to **[DeepSeek V4.1 Flash](https://app.fireworks.ai/models/fireworks/deepseek-v4p1-flash)**
* **[GLM 5.2](https://app.fireworks.ai/models/fireworks/glm-5p2)** — migrate to **[GLM 5.3](https://app.fireworks.ai/models/fireworks/glm-5p3)**
* **[Muse Glimmer 30B](https://app.fireworks.ai/models/fireworks/muse-glimmer-30b)** — migrate to **[NVIDIA Nemotron 3.5 Lightning 30B A3B](https://app.fireworks.ai/models/fireworks/nemotron-lightning-3p5-30b-a3b)**
* **[Kimi K2.6](https://app.fireworks.ai/models/fireworks/kimi-k2p6)** — migrate to **[GLM 5.3](https://app.fireworks.ai/models/fireworks/glm-5p3)** or **[Kimi K3](https://app.fireworks.ai/models/fireworks/kimi-k3)**
* **[Kimi K2.7 Code](https://app.fireworks.ai/models/fireworks/kimi-k2p7-code)** — migrate to **[GLM 5.3](https://app.fireworks.ai/models/fireworks/glm-5p3)** or **[Kimi K3](https://app.fireworks.ai/models/fireworks/kimi-k3)**

On official benchmarks, DeepSeek V4.1 Flash outperforms DeepSeek V4 Pro (0813). DeepSeek V4.1 Flash is also multimodal, with the same vision capability as DeepSeek V4 Flash Vision Exp.

If you want to switch to a dedicated deployment, see the [Serverless model list](https://fireworks.ai/models?modelTypes=Serverless) and the [on-demand deployment quickstart](https://docs.fireworks.ai/getting-started/ondemand-quickstart.md).

**2026-08-27**

Inference

# Serverless deprecation: MiniMax M2.7, GPT OSS 20B, Kimi K2.6 Turbo/Fast, Kimi K2.7 Code Fast, DeepSeek V4 Pro

The following models are deprecated from serverless effective August 27, 2026.

## **Recommended migrations**

* **[MiniMax M2.7](https://app.fireworks.ai/models/fireworks/minimax-m2p7)** — migrate to **[MiniMax M3](https://app.fireworks.ai/models/fireworks/minimax-m3)**
* **[GPT OSS 20B](https://app.fireworks.ai/models/fireworks/gpt-oss-20b)** — migrate to **[GPT OSS 120B](https://app.fireworks.ai/models/fireworks/gpt-oss-120b)** or **[Qwen3 8B](https://app.fireworks.ai/models/fireworks/qwen3-8b)** for lower-latency workloads
* **[Kimi K2.6 Turbo / Fast](https://app.fireworks.ai/models/fireworks/kimi-k2p6)** — migrate to **[Kimi K2.6](https://app.fireworks.ai/models/fireworks/kimi-k2p6)** (standard mode)
* **[Kimi K2.7 Code Fast](https://app.fireworks.ai/models/fireworks/kimi-k2p7-code)** — migrate to **[Kimi K2.7 Code](https://app.fireworks.ai/models/fireworks/kimi-k2p7-code)** (standard mode)
* **[DeepSeek V4 Pro](https://app.fireworks.ai/models/fireworks/deepseek-v4-pro)** — migrate to **[DeepSeek V4 Pro (0813)](https://app.fireworks.ai/models/fireworks/deepseek-v4-pro-0813)**

**2026-08-26**

Training

# Serverless Training deprecation: Qwen 3.5 9B and Qwen 3.6 27B

**Qwen 3.5 9B** and **Qwen 3.6 27B** are deprecated from Serverless Training effective August 26, 2026.

Migrate new and existing Serverless Training workloads to **[Qwen 3.8 27B](https://app.fireworks.ai/models/fireworks/qwen3p8-27b)**.

This change applies to the shared Serverless Training pool. Check the [training model catalog](https://docs.fireworks.ai/fine-tuning/models.md) for availability on other training surfaces.

**2026-08-14**

Inference

# Serverless deprecation: DeepSeek V4 Flash

**DeepSeek V4 Flash** is deprecated from serverless. Migrate to **[DeepSeek V4 Flash (0731)](https://app.fireworks.ai/models/fireworks/deepseek-v4-flash-0731)**.

**2026-06-26**

Inference

# Serverless deprecation: Kimi K2.5 and Qwen 3.6 Plus

**Kimi K2.5** and **Qwen 3.6 Plus** are deprecated from serverless.

## **Recommended migrations**

* **[Kimi K2.5](https://app.fireworks.ai/models/fireworks/kimi-k2p5)** — migrate to **[Kimi K2.6](https://app.fireworks.ai/models/fireworks/kimi-k2p6)**
* **[Qwen 3.6 Plus](https://app.fireworks.ai/models/fireworks/qwen3p6-plus)** — migrate to **[Qwen 3.7 Plus](https://app.fireworks.ai/models/fireworks/qwen3p7-plus)**

**2026-06-17**

Inference

# Serverless deprecation: MiniMax M2.5

**MiniMax M2.5** is deprecated from serverless. Migrate to **[MiniMax M2.7](https://app.fireworks.ai/models/fireworks/minimax-m2p7)**.

**2026-06-15**

Inference

# New model: GLM 5.2

**[GLM 5.2](https://app.fireworks.ai/models/fireworks/glm-5p2)** is now available in the Model Library.

**2026-06-10**

Inference

# Audio inference and image generation deprecation

Audio inference and image generation are deprecated.

**2026-05-14**

Inference

# Serverless deprecation: legacy models removed May 14, 2026

Several legacy serverless models will be decommissioned on **May 14, 2026** to make room for newer, higher-performance releases. This applies **only to serverless** usage; **dedicated deployments are unaffected**.

## **Action required**

If you use any of the models below on serverless, migrate to a recommended replacement **before May 14, 2026**. After that date, they will no longer be available via serverless endpoints.

## **Serverless migration guide**

* **DeepSeek V3.1** — migrate to **[Kimi K2.6](https://app.fireworks.ai/models/fireworks/kimi-k2p6)** or **[GLM 5.1](https://app.fireworks.ai/models/fireworks/glm-5p1)**
* **DeepSeek V3.2** — migrate to **[Kimi K2.6](https://app.fireworks.ai/models/fireworks/kimi-k2p6)** or **[GLM 5.1](https://app.fireworks.ai/models/fireworks/glm-5p1)**
* **GLM 4.7** — migrate to **[GLM 5.1](https://app.fireworks.ai/models/fireworks/glm-5p1)**
* **GLM 5** — migrate to **[GLM 5.1](https://app.fireworks.ai/models/fireworks/glm-5p1)**
* **Qwen3 8B** — migrate to **[GPT-OSS 20B](https://app.fireworks.ai/models/fireworks/gpt-oss-20b)**
* **Qwen3 VL 30B A3B Thinking** — migrate to **[Kimi K2.6](https://app.fireworks.ai/models/fireworks/kimi-k2p6)**
* **Qwen3 VL 30B A3B Instruct** — migrate to **[Kimi K2.6](https://app.fireworks.ai/models/fireworks/kimi-k2p6)**
* **Llama 3.3 70B Instruct** — migrate to **[GPT-OSS 120B](https://app.fireworks.ai/models/fireworks/gpt-oss-120b)**

We are continuing to invest in faster, more capable models and appreciate your support during this transition.
