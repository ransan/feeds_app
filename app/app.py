from fastapi import FastAPI, HTTPException, UploadFile, Form, Depends, File
from app.schemas import PostCreate, PostResponse, UserCreate, UserRead, UserUpdate
from app.db import Post, create_db_and_tables, get_async_session, User
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from  sqlalchemy import select
from app.images import imagekit
import shutil
import os
import tempfile
import uuid
from app.users import current_active_user, auth_backend, fast_api_users

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(
    fast_api_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"]
)
app.include_router(
    fast_api_users.get_register_router(UserRead, UserCreate), 
    prefix="/auth", 
    tags=["auth"]
)

app.include_router(
    fast_api_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"]
)

app.include_router(
    fast_api_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"]
)

app.include_router(
    fast_api_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"]
)

"""
posts = {
    1: {"title": "Start Before You Feel Ready", "content": "You don’t need perfect conditions to begin. Progress starts with taking the first step, even when you feel unsure. Action builds confidence, not the other way around."},
    
    2: {"title": "Consistency Beats Motivation", "content": "Motivation comes and goes, but consistency creates results. Focus on showing up every day, even in small ways, and success will follow."},
    
    3: {"title": "Learn Something Daily", "content": "Spend at least 30 minutes each day learning a new skill or improving an existing one. Over time, this compounds into massive growth."},
    
    4: {"title": "Focus on What Matters", "content": "Not everything deserves your attention. Identify high-impact tasks and give them your energy instead of getting lost in busy work."},
    
    5: {"title": "Embrace Failure as Feedback", "content": "Failure is not the opposite of success—it’s part of the journey. Every mistake teaches you something valuable if you’re willing to learn."},
    
    6: {"title": "Take Care of Your Health", "content": "Your body and mind are your greatest assets. Regular exercise, good sleep, and healthy food improve both productivity and happiness."},
    
    7: {"title": "Deep Work Matters", "content": "Eliminate distractions and focus deeply on one task at a time. Deep work produces higher quality results in less time."},
    
    8: {"title": "Build Strong Habits", "content": "Your habits shape your future. Start with small, manageable habits and stay consistent to create long-term change."},
    
    9: {"title": "Stay Curious", "content": "Curiosity keeps your mind active and open to new opportunities. Ask questions, explore ideas, and never stop learning."},
    
    10: {"title": "Value Time Over Everything", "content": "Time is the only resource you can’t get back. Spend it wisely on things that truly matter to you."},
    
    11: {"title": "Communicate Clearly", "content": "Clear communication avoids misunderstandings and builds stronger relationships, both personally and professionally."},
    
    12: {"title": "Keep Things Simple", "content": "Complexity creates confusion. Simplify your work and your life wherever possible to improve clarity and efficiency."},
    
    13: {"title": "Invest in Yourself", "content": "Skills, knowledge, and experience are the best investments you can make. They pay returns for a lifetime."},
    
    14: {"title": "Adapt to Change", "content": "The world is constantly evolving. Being flexible and open to change helps you stay relevant and resilient."},
    
    15: {"title": "Take Breaks to Recharge", "content": "Rest is not wasted time. Taking breaks helps you recharge, think clearly, and maintain long-term productivity."}
}


@app.get("/hello")
def hello():
    return {"message": "Hello, World!"}


@app.get("/posts")
def get_posts(limit: int = None):
    if limit:
        return {k: v for k, v in list(posts.items())[:limit]}
    return posts

@app.get("/posts/{post_id}")
def get_post(post_id: int) -> PostResponse:
    post = posts.get(post_id)
    if post:
        return post
    else:
        raise HTTPException(status_code=404, detail="Post not found")
    

@app.post("/posts")
def create_post(post: PostCreate) -> PostResponse:
    new_post = {"title": post.title, "content": post.content}
    posts[max(posts.keys()) + 1] = new_post
    return new_post
"""

@app.post("/upload")
async def upload_file(
    file: UploadFile= File(...), 
    caption: str = Form(""), 
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)):
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(file.filename)[1]
        ) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)

        response = imagekit.files.with_raw_response.upload(
            file=open(temp_file_path, "rb"),
            file_name=file.filename,
            use_unique_file_name=True,
            tags=["feed_app_backend_upload"],
        )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Upload failed")

        upload_result = response.parse()

        post = Post(
            user_id=user.id,
            caption=caption,
            url=upload_result.url,
            file_type="video" if file.content_type.startswith("video/") else "image",
            file_name=upload_result.name
        )
        session.add(post)
        await session.commit()
        await session.refresh(post)
        return post
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            file.file.close()


@app.get("/feed")
async def get_feed(session: AsyncSession = Depends(get_async_session), user: User = Depends(current_active_user)):
    result = await session.execute(select(Post).order_by(Post.created_at.desc()))
    posts = [row[0] for row in result.all()]
    posts_data = []
    for post in posts:
        posts_data.append({
            "id": str(post.id),
            "user_id": str(post.user_id) if post.user_id is not None else None,
            "caption": post.caption,
            "url": post.url,
            "file_type": post.file_type,
            "file_name": post.file_name,
            "created_at": post.created_at.isoformat(),
            "is_owner": post.user_id == user.id,
            #"email": post.user.email
        })
    return {"posts": posts_data }




@app.delete("/posts/{post_id}")
async def delete_post(post_id: str, session: AsyncSession = Depends(get_async_session), user: User = Depends(current_active_user)):
    try:
        post_uuid = uuid.UUID(post_id)
        result = await session.execute(select(Post).where(Post.id == post_uuid))
        post = result.scalars().first()

        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        if post.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this post")

        await session.delete(post)
        await session.commit()
        return {"success": True, "message": "Post deleted successfully"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid post ID format")   

    
