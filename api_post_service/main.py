import os
from datetime import datetime
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
import grpc

from pydantic import BaseModel, Field
from typing import List

import post_pb2
import post_pb2_grpc

SECRET_KEY = os.getenv("SECRET_KEY", "MY_SECRET_KEY")
ALGORITHM = "HS256"

GRPC_SERVER_ADDR = os.getenv("GRPC_POST_SERVICE", "localhost:50051")

channel = grpc.insecure_channel(GRPC_SERVER_ADDR)
stub = post_pb2_grpc.PostServiceStub(channel)

app = FastAPI(
    title="API Post Service",
    version="1.0.0"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


class PostCreate(BaseModel):
    title: str
    description: str
    is_private: bool = False
    tags: List[str] = Field(default_factory=list)

class PostUpdate(BaseModel):
    title: Optional[str]
    description: Optional[str]
    is_private: Optional[bool]
    tags: Optional[List[str]]

class PostOut(BaseModel):
    id: str
    title: str
    description: str
    creator_id: str
    created_at: datetime
    updated_at: datetime
    is_private: bool
    tags: List[str]

class PostListOut(BaseModel):
    posts: List[PostOut]
    total: int
    page: int
    page_size: int

class CommentOut(BaseModel):
    id: str
    author_id: str
    text: str
    created_at: datetime

class CommentIn(BaseModel):
    text: str = Field(..., min_length=1)


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")  # sub = логин или ID пользователя
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    return user_id

@app.post("/posts", response_model=PostOut, status_code=201)
def create_post(post_in: PostCreate, user_id: str = Depends(get_current_user_id)):
    try:
        resp = stub.CreatePost(post_pb2.CreatePostRequest(
            user_id=user_id,
            title=post_in.title,
            description=post_in.description,
            is_private=post_in.is_private,
            tags=post_in.tags
        ))
        return _post_to_postout(resp.post)
    except grpc.RpcError as e:
        raise _grpc_error_to_http(e)

@app.get("/posts/{post_id}", response_model=PostOut)
def get_post(post_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        resp = stub.GetPost(post_pb2.GetPostRequest(
            user_id=user_id,
            post_id=post_id
        ))
        return _post_to_postout(resp.post)
    except grpc.RpcError as e:
        raise _grpc_error_to_http(e)

@app.put("/posts/{post_id}", response_model=PostOut)
def update_post(
    post_id: str,
    post_in: PostUpdate,
    user_id: str = Depends(get_current_user_id)
):
    try:
        resp = stub.UpdatePost(post_pb2.UpdatePostRequest(
            user_id=user_id,
            post_id=post_id,
            title=post_in.title or "",
            description=post_in.description or "",
            is_private=post_in.is_private or False,
            tags=post_in.tags or []
        ))
        return _post_to_postout(resp.post)
    except grpc.RpcError as e:
        raise _grpc_error_to_http(e)

@app.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        stub.DeletePost(post_pb2.DeletePostRequest(
            user_id=user_id,
            post_id=post_id
        ))
        return
    except grpc.RpcError as e:
        raise _grpc_error_to_http(e)

@app.get("/posts", response_model=PostListOut)
def list_posts(
    page: int = 1,
    page_size: int = 10,
    user_id: str = Depends(get_current_user_id)
):
    try:
        resp = stub.ListPosts(post_pb2.ListPostsRequest(
            user_id=user_id,
            page=page,
            page_size=page_size
        ))
        return PostListOut(
            posts=[_post_to_postout(p) for p in resp.posts],
            total=resp.total,
            page=resp.page,
            page_size=resp.page_size
        )
    except grpc.RpcError as e:
        raise _grpc_error_to_http(e)

def _post_to_postout(p: post_pb2.Post) -> PostOut:
    return PostOut(
        id=p.id,
        title=p.title,
        description=p.description,
        creator_id=p.creator_id,
        created_at=p.created_at.ToDatetime(),
        updated_at=p.updated_at.ToDatetime(),
        is_private=p.is_private,
        tags=list(p.tags)
    )

def _grpc_error_to_http(e: grpc.RpcError) -> HTTPException:
    code = e.code()
    if code == grpc.StatusCode.NOT_FOUND:
        raise HTTPException(status_code=404, detail=e.details())
    elif code == grpc.StatusCode.PERMISSION_DENIED:
        raise HTTPException(status_code=403, detail=e.details())
    elif code == grpc.StatusCode.INVALID_ARGUMENT:
        raise HTTPException(status_code=400, detail=e.details())
    else:
        raise HTTPException(status_code=500, detail=e.details())

@app.post("/posts/{post_id}/view", status_code=204)
def view_post(post_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        stub.ViewPost(post_pb2.ViewPostRequest(user_id=user_id, post_id=post_id))
    except grpc.RpcError as e:
        raise _grpc_error_to_http(e)


@app.post("/posts/{post_id}/like", status_code=204)
def like_post(post_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        stub.LikePost(post_pb2.LikePostRequest(user_id=user_id, post_id=post_id))
    except grpc.RpcError as e:
        raise _grpc_error_to_http(e)


@app.post("/posts/{post_id}/comments", response_model=CommentOut, status_code=201)
def create_comment(
    post_id: str,
    payload: CommentIn,
    user_id: str = Depends(get_current_user_id)
):
    try:
        resp = stub.CommentPost(post_pb2.CommentPostRequest(
            user_id=user_id, post_id=post_id, text=payload.text))
        c = resp.comment
        return CommentOut(
            id=c.id, author_id=c.author_id,
            text=c.text, created_at=c.created_at.ToDatetime()
        )
    except grpc.RpcError as e:
        raise _grpc_error_to_http(e)


class CommentListOut(BaseModel):
    comments: List[CommentOut]
    total: int
    page: int
    page_size: int

@app.get("/posts/{post_id}/comments", response_model=CommentListOut)
def list_comments(
    post_id: str,
    page: int = 1,
    page_size: int = 20,
    user_id: str = Depends(get_current_user_id)
):
    try:
        resp = stub.ListComments(post_pb2.ListCommentsRequest(
            post_id=post_id, page=page, page_size=page_size))
        return CommentListOut(
            comments=[CommentOut(
                id=c.id, author_id=c.author_id,
                text=c.text, created_at=c.created_at.ToDatetime()
            ) for c in resp.comments],
            total=resp.total, page=resp.page, page_size=resp.page_size
        )
    except grpc.RpcError as e:
        raise _grpc_error_to_http(e)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)