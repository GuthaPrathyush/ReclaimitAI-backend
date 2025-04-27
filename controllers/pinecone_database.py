import jwt
from pinecone import Pinecone, ServerlessSpec
import os
from bson import ObjectId

pinecone_ref = Pinecone(api_key=os.getenv('PINECONE_API'))

lost_index_name_text = os.getenv('LOST_INDEX_NAME_TEXT')
found_index_name_text = os.getenv('FOUND_INDEX_NAME_TEXT')
lost_index_name_img = os.getenv('LOST_INDEX_NAME_IMG')
found_index_name_img = os.getenv('FOUND_INDEX_NAME_IMG')

my_pinecone_indexes = pinecone_ref.list_indexes()

my_pinecone_indexes_names = [index["name"] for index in my_pinecone_indexes]

if lost_index_name_text not in my_pinecone_indexes_names:
    pinecone_ref.create_index(
        name=lost_index_name_text,
        dimension=384,  # Set according to your embedding model
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

if found_index_name_text not in my_pinecone_indexes_names:
    pinecone_ref.create_index(
        name=found_index_name_text,
        dimension=384,  # Set according to your embedding model
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

if lost_index_name_img not in my_pinecone_indexes_names:
    pinecone_ref.create_index(
        name=lost_index_name_img,
        dimension=768,  # Set according to your embedding model
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

if found_index_name_img not in my_pinecone_indexes_names:
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
    return lost_index_text_ref.query(vector=vector_embedding, top_k=5)

def query_found_item_description_in_pinecone_database(vector_embedding):
    return found_index_text_ref.query(vector=vector_embedding, top_k=5)

def query_lost_item_image_in_pinecone_database(vector_embedding):
    return lost_index_img_ref.query(vector=vector_embedding, top_k=5)

def query_found_item_image_in_pinecone_database(vector_embedding):
    return found_index_img_ref.query(vector=vector_embedding, top_k=5)

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


def get_matched_lost_items_id(text_embedding, image_embedding):
    res = set()

    matched_lost_text = query_lost_item_description_in_pinecone_database(text_embedding)
    matched_lost_text_list = matched_lost_text.get('matches', [])
    for match in matched_lost_text_list:
        res.add(match['id'])

    matched_lost_image = query_lost_item_image_in_pinecone_database(image_embedding)
    matched_lost_image_list = matched_lost_image.get('matches', [])
    for match in matched_lost_image_list:
        res.add(match['id'])

    return list(res)

def get_matched_found_items_id(text_embedding, image_embedding):
    res = set()

    matched_found_text = query_found_item_description_in_pinecone_database(text_embedding)
    matched_found_text_list = matched_found_text.get('matches', [])
    for match in matched_found_text_list:
        res.add(match)

    matched_found_image = query_found_item_image_in_pinecone_database(image_embedding)
    matched_found_image_list = matched_found_image.get('matches', [])
    for match in matched_found_image_list:
        res.add(match)

    return list(res)
