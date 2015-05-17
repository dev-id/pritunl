from pritunl.organization.organization import Organization

from pritunl.constants import *
from pritunl.exceptions import *
from pritunl.helpers import *
from pritunl import logger
from pritunl import queue
from pritunl import user
from pritunl import mongo

import threading

def new_pooled():
    thread = threading.Thread(target=new_org, kwargs={
        'type': ORG_POOL,
        'block': False,
    })
    thread.daemon = True
    thread.start()

    logger.debug('Queued pooled org', 'organization')

def reserve_pooled(name=None, type=ORG_DEFAULT):
    doc = {}

    if name is not None:
        doc['name'] = name
    if type is not None:
        doc['type'] = type

    doc = Organization.collection.find_and_modify({
        'type': ORG_POOL,
    }, {
        '$set': doc,
    }, new=True)

    if doc:
        return Organization(doc=doc)

def new_org(type=ORG_DEFAULT, block=True, **kwargs):
    if type == ORG_DEFAULT:
        org = reserve_pooled(type=type, **kwargs)

        if not org:
            org = queue.reserve('queued_org', block=block, type=type,
                **kwargs)

            if org:
                logger.debug('Reserved queued org', 'organization',
                    org_id=org.id,
                )
        else:
            logger.debug('Reserved pooled org', 'organization',
                org_id=org.id,
            )

        if org:
            new_pooled()
            return org

        org = Organization(type=type, **kwargs)
        org.initialize()
        org.commit()

        logger.debug('Org init', 'organization',
            org_id=org.id,
        )

        return org
    else:
        org = Organization(type=type, **kwargs)
        org.queue_initialize(block=block)

        logger.debug('Queue org init', 'organization',
            org_id=org.id,
        )

        return org

def get_by_id(id, fields=None):
    return Organization(id=id, fields=fields)

def iter_orgs(spec=None, type=ORG_DEFAULT, fields=None):
    if spec is None:
        spec = {}
    if type is not None:
        spec['type'] = type

    if fields:
        fields = {key: True for key in fields}

    for doc in Organization.collection.find(spec, fields).sort('name'):
        yield Organization(doc=doc, fields=fields)

def iter_orgs_dict():
    spec = {
        'type': ORG_DEFAULT,
    }

    for doc in Organization.collection.find(spec).sort('name'):
        org = Organization(doc=doc)
        yield org.dict()

def get_user_count(org_ids, type=CERT_CLIENT):
    user_collection = mongo.get_collection('users')
    org_user_count = {}

    for org_id in org_ids:
        org_user_count[org_id] = user_collection.find({
            'type': type,
            'org_id': org_id,
        }, {
            '_id': True,
        }).count()

    return org_user_count

def get_user_count_multi(org_ids=None, type=CERT_CLIENT):
    spec = {
        'type': type,
    }
    if org_ids is not None:
        spec['org_id'] = {'$in': org_ids}
    return user.User.collection.find(spec, {
        '_id': True,
    }).count()
