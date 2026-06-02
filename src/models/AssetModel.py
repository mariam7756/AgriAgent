from .BaseDataModel import BaseDataModel
from .db_schemes import Asset

from sqlalchemy.future import select

class AssetModel(BaseDataModel):

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.collection = db_client

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        
        return instance

    
    async def create_asset(self, asset: Asset) -> int:
        async with self.collection() as session:
            async with session.begin():
                session.add(asset)
                await session.flush()
                asset_id = asset.asset_id
        return asset_id
                    

        
    async def get_all_project_assets(self, asset_project_id: str, asset_type: str):
        async with self.collection() as session:
            stmt = select(Asset).where(
                Asset.asset_project_id == asset_project_id,
                Asset.asset_type == asset_type
            )
            result = await session.execute(stmt)
            records = result.scalars().all()
        return records

       
    async def get_asset_record(self, asset_project_id: str, asset_name: str):
        async with self.collection() as session:
            stmt = select(Asset).where(
                Asset.asset_project_id == asset_project_id,
                Asset.asset_name == asset_name
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
        return record
    
    async def get_web_asset_by_source_url(self, asset_project_id: int, source_url: str):
        async with self.collection() as session:
            stmt = select(Asset).where(
                Asset.asset_project_id == asset_project_id,
                Asset.asset_type == "web",
                Asset.asset_config.contains({"source_url": source_url}),
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
        return record
            
    async def get_web_asset_by_source_url(self, asset_project_id: int, source_url: str):
        async with self.collection() as session:
            stmt = select(Asset).where(
                Asset.asset_project_id == asset_project_id,
                Asset.asset_type == "web",
                Asset.asset_config.contains({"source_url": source_url}),
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
        return record
    
    
    async def update_asset(self, asset: Asset):
        async with self.collection() as session:
            async with session.begin():
                await session.merge(asset)
            await session.commit()
            await session.refresh(asset)
        return asset
        

        

    