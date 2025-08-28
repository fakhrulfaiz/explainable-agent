from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
import asyncio, json, base64
import os
from pathlib import Path

router = APIRouter(
    prefix="/stream",
    tags=["stream"]
)

@router.post("/chat")
async def chat():
    async def event_generator():
        print("[DEBUG] Starting streaming response...")
        
        # Step 1: send text response
        text_msg = {"type": "text", "data": "This is a cat image"}
        print(f"[DEBUG] Sending text: {text_msg}")
        yield json.dumps(text_msg) + "\n"
        await asyncio.sleep(1)  # simulate delay

        # Step 2: send image (cat.jpeg from resources folder)
        # Try multiple possible paths for cat.jpeg
        possible_paths = [
            "cat.jpeg",
            "routers/cat.jpeg", 
            "./cat.jpeg",
            Path("cat.jpeg").resolve(),
            Path("backend/cat.jpeg").resolve()
        ]
        
        img_bytes = None
        for path in possible_paths:
            try:
                print(f"[DEBUG] Trying to open: {path}")
                with open(path, "rb") as f:
                    img_bytes = f.read()
                print(f"[DEBUG] Successfully loaded image from: {path} (size: {len(img_bytes)} bytes)")
                break
            except FileNotFoundError:
                continue
        
        if img_bytes is None:
            print("[DEBUG] No cat.jpeg found, using placeholder")
            # Fallback: create a simple placeholder image
            img_bytes = base64.b64decode(
                "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/2wBDAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQH/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwA/AP/Z"
            )

        img_b64 = base64.b64encode(img_bytes).decode()
        print(f"[DEBUG] Base64 image length: {len(img_b64)}")

        # stream in chunks for simulation
        chunk_size = 2000
        total_chunks = (len(img_b64) + chunk_size - 1) // chunk_size
        print(f"[DEBUG] Streaming image in {total_chunks} chunks")
        
        for i in range(0, len(img_b64), chunk_size):
            chunk = img_b64[i:i+chunk_size]
            chunk_msg = {"type": "image_chunk", "data": chunk}
            print(f"[DEBUG] Sending chunk {(i//chunk_size)+1}/{total_chunks} (size: {len(chunk)})")
            yield json.dumps(chunk_msg) + "\n"
            await asyncio.sleep(0.1)

        # final message
        done_msg = {"type": "done"}
        print(f"[DEBUG] Sending done message: {done_msg}")
        yield json.dumps(done_msg) + "\n"
        print("[DEBUG] Streaming complete!")

    return StreamingResponse(
        event_generator(), 
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )
