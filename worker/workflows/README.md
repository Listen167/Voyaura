# ComfyUI workflows

Export the ComfyUI workflow with **Save (API Format)** and keep the JSON outside
source control when it contains local model names or private paths. Configure:

- `VOYAURA_IMAGE_PROVIDER=comfyui`
- `VOYAURA_COMFYUI_WORKFLOW_PATH=D:\path\to\workflow-api.json`
- `VOYAURA_COMFYUI_INPUT_NODE_ID`: `LoadImage` node receiving the source photo
- `VOYAURA_COMFYUI_POSITIVE_PROMPT_NODE_ID`: positive `CLIPTextEncode` node
- `VOYAURA_COMFYUI_NEGATIVE_PROMPT_NODE_ID`: optional negative prompt node
- `VOYAURA_COMFYUI_OUTPUT_NODE_ID`: optional `SaveImage` or `PreviewImage` node

The configured workflow must accept an uploaded image in the input node and
produce at least one image. Voyaura uploads the private source from the backend,
waits on `/history/{prompt_id}`, downloads the output through `/view`, removes
metadata by re-encoding to WebP, and stores it in private MinIO.
