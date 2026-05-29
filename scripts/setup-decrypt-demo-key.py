import asyncio, os
import asyncpg
import redis.asyncio as aioredis
import app.infra.globals as g
from uuid import UUID

INV = UUID("019e485a-e5fa-71a2-8c6f-5abb9c4cd33b")
PLAIN = "glow-demo-key-DO-NOT-USE-9f3a2c"

async def main():
    g.redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)
    from app.infra.globals import get_redis_client
    from app.tools.resources.keys.create import create_key
    from app.utils.auth.encrypt_api_key import encrypt_api_key
    from app.tools.entries.invocation.get import get_invocations
    pw = os.environ["DB_PASSWORD"]
    conn = await asyncpg.connect(host="localhost",port=5432,user="myuser",password=pw,database="glowapi")
    redis = get_redis_client()
    enc = encrypt_api_key(PLAIN)
    key = await create_key(conn, redis, name="Demo Decrypt Key", key=enc, description="Throwaway key for the tests-decrypt demo")
    kid = key.id
    await conn.execute("INSERT INTO invocation_keys_connection (invocation_id, keys_id, active, generated, mcp) VALUES ($1,$2,true,false,false) ON CONFLICT DO NOTHING", INV, kid)
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY invocation_mv")
    invs = await get_invocations(conn, [INV], redis, bypass_cache=True)
    print("invocation key_ids:", [str(k) for k in (invs[0].key_ids if invs else [])])
    print("KEY_ID="+str(kid))
    print("INV="+str(INV))
    await conn.close()

asyncio.run(main())
