import grpc
from concurrent import futures
from datetime import datetime
from google.protobuf import empty_pb2
from google.protobuf import timestamp_pb2

import post_pb2
import post_pb2_grpc

from common.kafka import send

class PostServiceServicer(post_pb2_grpc.PostServiceServicer):
    def __init__(self):
        self.posts = {}
        self.next_id = 1
        self.views = set()
        self.likes = set()

    def CreatePost(self, request, context):
        now = datetime.utcnow()
        post_id = str(self.next_id)
        self.next_id += 1

        post = post_pb2.Post(
            id=post_id,
            title=request.title,
            description=request.description,
            creator_id=request.user_id,
            created_at=self._to_ts(now),
            updated_at=self._to_ts(now),
            is_private=request.is_private,
            tags=request.tags
        )
        self.posts[post_id] = post
        return post_pb2.CreatePostResponse(post=post)

    def GetPost(self, request, context):
        post = self.posts.get(request.post_id)
        if not post:
            context.abort(grpc.StatusCode.NOT_FOUND, "Post not found")
        if post.is_private and post.creator_id != request.user_id:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "Access denied")
        return post_pb2.GetPostResponse(post=post)

    def UpdatePost(self, request, context):
        post = self.posts.get(request.post_id)
        if not post:
            context.abort(grpc.StatusCode.NOT_FOUND, "Post not found")
        if post.creator_id != request.user_id:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "You can update only your own post")

        now = datetime.utcnow()
        updated_post = post_pb2.Post(
            id=post.id,
            title=request.title if request.title else post.title,
            description=request.description if request.description else post.description,
            creator_id=post.creator_id,
            created_at=post.created_at,
            updated_at=self._to_ts(now),
            is_private=request.is_private,
            tags=request.tags if request.tags else post.tags
        )
        self.posts[post.id] = updated_post
        return post_pb2.UpdatePostResponse(post=updated_post)

    def DeletePost(self, request, context):
        post = self.posts.get(request.post_id)
        if not post:
            context.abort(grpc.StatusCode.NOT_FOUND, "Post not found")
        if post.creator_id != request.user_id:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "You can delete only your own post")

        del self.posts[request.post_id]
        return empty_pb2.Empty()

    def ListPosts(self, request, context):
        all_posts = []
        for p in self.posts.values():
            # Если приватный пост, а user_id не совпадает – скрываем
            if p.is_private and p.creator_id != request.user_id:
                continue
            all_posts.append(p)

        all_posts.sort(key=lambda x: x.created_at.seconds, reverse=True)
        total = len(all_posts)

        page = request.page if request.page > 0 else 1
        page_size = request.page_size if request.page_size > 0 else 10
        start = (page - 1) * page_size
        end = start + page_size

        return post_pb2.ListPostsResponse(
            posts=all_posts[start:end],
            total=total,
            page=page,
            page_size=page_size
        )

    def _to_ts(self, dt: datetime):
        ts = timestamp_pb2.Timestamp()
        ts.FromDatetime(dt)
        return ts

    def ViewPost(self, request, context):
        key = (request.user_id, request.post_id)
        if key not in self.views:
            self.views.add(key)
            send("post-views", {
                "user_id": request.user_id,
                "post_id": request.post_id,
                "ts": datetime.utcnow().isoformat()
            })
        return empty_pb2.Empty()

    def LikePost(self, request, context):
        key = (request.user_id, request.post_id)
        if key not in self.likes:
            self.likes.add(key)
            send("post-likes", {
                "user_id": request.user_id,
                "post_id": request.post_id,
                "ts": datetime.utcnow().isoformat()
            })
        return empty_pb2.Empty()

    def CommentPost(self, request, context):
        comment_id = str(len(self.comments.get(request.post_id, [])) + 1)
        now = datetime.utcnow()
        comment = post_pb2.Comment(
            id=comment_id,
            post_id=request.post_id,
            author_id=request.user_id,
            text=request.text,
            created_at=self._to_ts(now)
        )
        self.comments.setdefault(request.post_id, []).append(comment)

        send("post-comments", {
            "user_id": request.user_id,
            "post_id": request.post_id,
            "comment_id": comment_id,
            "ts": now.isoformat()
        })
        return post_pb2.CommentPostResponse(comment=comment)

    def ListComments(self, request, context):
        all_comments = self.comments.get(request.post_id, [])
        start = (request.page - 1) * request.page_size
        end = start + request.page_size
        return post_pb2.ListCommentsResponse(
            comments=all_comments[start:end],
            total=len(all_comments),
            page=request.page,
            page_size=request.page_size
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    post_pb2_grpc.add_PostServiceServicer_to_server(PostServiceServicer(), server)

    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC post service started on port 50051...")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()