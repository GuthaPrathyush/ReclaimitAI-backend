from transformers import ViTImageProcessor, ViTModel
from sentence_transformers import SentenceTransformer
from PIL import Image
import torch
from fastapi import UploadFile
import io

# Load Model & Processor once globally (optional for performance)
model = ViTModel.from_pretrained("google/vit-base-patch16-224-in21k")
image_processor = ViTImageProcessor.from_pretrained("google/vit-base-patch16-224-in21k")

# Load model once globally (for performance)
text_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

async def get_image_embedding(file: UploadFile):
    # Read image bytes from UploadFile
    image_bytes = await file.read()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Process image
    inputs = image_processor(images=image, return_tensors="pt")

    # Generate embedding using ViT
    with torch.no_grad():
        outputs = model(**inputs)

    # Extract CLS token as embedding
    embedding = outputs.last_hidden_state[:, 0, :]  # Shape: (1, 768)
    return embedding.squeeze().tolist()


async def get_text_embedding(text: str):
    embedding = text_model.encode(text)
    return embedding
