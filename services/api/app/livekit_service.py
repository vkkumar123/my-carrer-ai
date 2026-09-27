import json

from livekit import api

from app.config import get_settings


def participant_token(*, room: str, identity: str, name: str, round_id: str) -> str:
    """Token for the candidate that also dispatches the interviewer agent into the room."""
    s = get_settings()
    return (
        api.AccessToken(s.livekit_api_key, s.livekit_api_secret)
        .with_identity(identity)
        .with_name(name)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(
                        agent_name=s.livekit_agent_name,
                        metadata=json.dumps({"round_id": round_id}),
                    )
                ]
            )
        )
        .to_jwt()
    )
