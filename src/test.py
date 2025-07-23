from vllm import LLM, SamplingParams

prompts = [
    "Hello, how are you?",
    "What is the capital of France?",
    "Where is Vietnam?"
]

llm = LLM(model="facebook/opt-125m")

sampling_params = SamplingParams(temperature=0.6, top_p=0.95, max_tokens=256)

outputs = llm.generate(prompts, sampling_params)

for output in outputs:
    print(f"prompt: {output.prompt}, output: {output.text}")