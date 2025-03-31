from dotenv import load_dotenv, find_dotenv
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
import os
from datetime import datetime, timezone

#**********************text_embedding************************
# from sentence_transformers import SentenceTransformer
# model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
# text = "A black Adidas backpack with zippers."
#
# embedding = model.encode(text)
#
# print(embedding.shape)  # Output: (384,)
# print(embedding)

#**********************IMAGE embedding***************************
# from transformers import ViTImageProcessor, ViTModel
# from PIL import Image
# import torch
#
# # Load Model & Image Processor
# model = ViTModel.from_pretrained("google/vit-base-patch16-224-in21k")
# image_processor = ViTImageProcessor.from_pretrained("google/vit-base-patch16-224-in21k")
#
# # Load Image and Convert to RGB
# image = Image.open("image.png").convert("RGB")  # Ensure RGB mode
#
# # Process Image (Wrap in a List)
# inputs = image_processor(images=[image], return_tensors="pt")  # List format required
#
# # Extract Image Embedding
# with torch.no_grad():
#     outputs = model(**inputs)
#
# # Use CLS token as the image embedding (1, 768)
# image_embedding = outputs.last_hidden_state[:, 0, :]
#
# print(image_embedding.shape)  # Expected Output: (1, 768)
# print(image_embedding)


env_path = find_dotenv() or find_dotenv('../.env')

load_dotenv(env_path)

pinecone_ref = Pinecone(api_key=os.getenv('PINECONE_API'))

lost_index_name_text = os.getenv('LOST_INDEX_NAME_TEXT')
found_index_name_text = os.getenv('FOUND_INDEX_NAME_TEXT')
lost_index_name_img = os.getenv('LOST_INDEX_NAME_IMG')
found_index_name_img = os.getenv('FOUND_INDEX_NAME_IMG')


if lost_index_name_text not in pinecone_ref.list_indexes():
    pinecone_ref.create_index(
        name=lost_index_name_text,
        dimension=384,  # Set according to your embedding model
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

if found_index_name_text not in pinecone_ref.list_indexes():
    pinecone_ref.create_index(
        name=found_index_name_text,
        dimension=384,  # Set according to your embedding model
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

if lost_index_name_img not in pinecone_ref.list_indexes():
    pinecone_ref.create_index(
        name=lost_index_name_img,
        dimension=768,  # Set according to your embedding model
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

if found_index_name_img not in pinecone_ref.list_indexes():
    pinecone_ref.create_index(
        name=found_index_name_img,
        dimension=768,  # Set according to your embedding model
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

lost_index_text_ref = pinecone_ref.Index(lost_index_name_text)
found_index_text_ref = pinecone_ref.Index(found_index_name_text)
lost_index_img_ref = pinecone_ref.Index(lost_index_name_img)
found_index_img_ref = pinecone_ref.Index(found_index_name_img)

#querying

def query_lost_item_description_in_pinecone_database(vector_embedding):
    lost_index_text_ref.query(vector=vector_embedding, top_k=5)

def query_found_item_description_in_pinecone_database(vector_embedding):
    found_index_text_ref.query(vector=vector_embedding, top_k=5)

def query_lost_item_image_in_pinecone_database(vector_embedding):
    lost_index_img_ref.query(vector=vector_embedding, top_k=5)

def query_found_item_image_in_pinecone_database(vector_embedding):
    found_index_img_ref.query(vector=vector_embedding, top_k=5)

#upserting

def upsert_lost_item_description_in_pinecone_database(post_id, vector_embedding):
    lost_index_text_ref.upsert([(post_id, vector_embedding)])

def upsert_found_item_description_in_pinecone_database(post_id, vector_embedding):
    found_index_text_ref.upsert([(post_id, vector_embedding)])

def upsert_lost_item_image_in_pinecone_database(post_id, vector_embedding):
    lost_index_img_ref.upsert([(post_id, vector_embedding)])

def upsert_found_item_image_in_pinecone_database(post_id, vector_embedding):
    found_index_img_ref.upsert([(post_id, vector_embedding)])

#deleting

def delete_lost_item_description_in_pinecone_database(post_id):
    lost_index_text_ref.delete(ids=[post_id])

def delete_found_item_description_in_pinecone_database(post_id):
    found_index_text_ref.delete(ids=[post_id])

def delete_lost_item_image_in_pinecone_database(post_id):
    lost_index_img_ref.delete(ids=[post_id])

def delete_found_item_image_in_pinecone_database(post_id):
    found_index_img_ref.delete(ids=[post_id])

