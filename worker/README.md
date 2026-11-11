# Voyaura Worker

This service will own asynchronous media work:

- photo normalization and thumbnails;
- vlog metadata and cover extraction;
- style generation through provider adapters;
- optional ComfyUI workflows;
- Xiaoxi co-photo composition;
- poster and publish-pack rendering.

No image provider is selected in the scaffold. The worker contract will keep
cloud editing models and ComfyUI interchangeable.

