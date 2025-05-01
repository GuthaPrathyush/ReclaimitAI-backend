# ReclaimitAI

> 🔗 **You can explore the frontend here:** [ReclaimitAI Frontend Repository](https://github.com/GuthaPrathyush/ReclaimitAI_Frontend)

ReclaimitAI is an AI-powered Lost and Found Portal designed to help users report and reclaim lost or found items. By leveraging natural language processing (NLP) and computer vision, ReclaimitAI matches lost item reports with found ones based on both text descriptions and images.


## How It Works

1. **Users Report Lost or Found Items**: Fill out a form with a description and optional image.
2. **AI Matching Engine**: Uses models like BERT and CLIP to generate embeddings and compare similarities.
3. **Automated Notifications**: Users are notified if a potential match is found.
4. **Verified Claim Process**: Contact info is exchanged securely for claim verification.

## Features

- Report lost or found items with details and images
- AI-powered matching using text and image embeddings
- Vector database for fast and accurate retrieval
- Real-time user notifications for matched items
- Simple authentication and user dashboard

## Tech Stack

- **Frontend**: React (with Vite)
- **Backend**: FastAPI
- **Database**: MongoDB + Pinecone (for vector search)
- **AI Models**: BERT (text), CLIP (images)
- **Storage**: Cloudinary 
- **Deployment**: Vercel (frontend), Render (backend)

### Prerequisites

- Python 3.8+ or Node.js (depending on backend)
- MongoDB instance
- API keys for OpenAI, Pinecone/Qdrant, and image storage