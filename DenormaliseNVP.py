#!/usr/bin/python
# -*- coding: utf-8 -*-

from builtins import chr
from sqlalchemy import *
from sqlalchemy import exc
import warnings
import sys
import os
import argparse
import uuid
import re

class UUID(TypeDecorator):
    """Platform-independent UUID type.

    Uses Postgresql's UUID type, otherwise uses
    CHAR(36), storing as stringified hex values.

    """
    impl = CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value)).upper()
            else:
                return str(value).upper()

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return uuid.UUID(value)

parser = argparse.ArgumentParser(description='Denormalise a normalised NVivo project.')
parser.add_argument('-w', '--windows', action='store_true',
                    help='Correct NVivo for Windows string coding. Use if offloaded file will be used with Windows version of NVivo.')
parser.add_argument('-s', '--structure', action='store_true',
                    help='Replace existing table structures.')

table_choices = ["", "skip", "replace", "merge"]
parser.add_argument('-p', '--project', choices=table_choices, default="replace",
                    help='Project action.')
parser.add_argument('-nc', '--node-categories', choices=table_choices, default="replace",
                    help='Node category action.')
parser.add_argument('-n', '--nodes', choices=table_choices, default="replace",
                    help='Node action.')
parser.add_argument('-na', '--node-attributes', choices=table_choices, default="replace",
                    help='Node attribute table action.')
parser.add_argument('-sc', '--source-categories', choices=table_choices, default="replace",
                    help='Source category action.')
parser.add_argument('--sources', choices=table_choices, default="replace",
                    help='Source action.')
parser.add_argument('-sa', '--source-attributes', choices=table_choices, default="replace",
                    help='Source attribute action.')
parser.add_argument('-t', '--taggings', choices=table_choices, default="replace",
                    help='Tagging action.')
parser.add_argument('-a', '--annotations', choices=table_choices, default="replace",
                    help='Annotation action.')
parser.add_argument('-u', '--users', choices=table_choices, default="replace",
                    help='User action.')

parser.add_argument('infile', type=str,
                    help='SQLAlchemy path of input normalised database.')
parser.add_argument('outfile', type=str, nargs='?',
                    help='SQLAlchemy path of input output NVivo database.')

args = parser.parse_args()

try:
    # Hide warning message over unrecognised xml columns
    warnings.filterwarnings("ignore", category=exc.SAWarning, message='Did not recognize type \'xml\'.*', module='sqlalchemy')

    normdb = create_engine(args.infile)
    normmd = MetaData(bind=normdb)
    normmd.reflect(normdb)

    if args.outfile is None:
        args.outfile = args.infile.rsplit('.',1)[0] + '.nvivo'
    nvivodb = create_engine(args.outfile)
    nvivomd = MetaData(bind=nvivodb)
    nvivomd.reflect(nvivodb)

    if args.structure:
        nvivomd.drop_all(nvivodb)
        for table in reversed(nvivomd.sorted_tables):
            nvivomd.remove(table)

    nvivoProject = nvivomd.tables.get('Project')
    if nvivoProject == None:
        nvivoProject = Table('Project', nvivomd,
            Column('Title',         String(256),    nullable=False),
            Column('Description',   String(512),    nullable=False),
            Column('CreatedBy',     UUID(),         nullable=False),
            Column('CreatedDate',   DateTime,       nullable=False),
            Column('ModifiedBy',    UUID(),         nullable=False),
            Column('ModifiedDate',  DateTime,       nullable=False))

    nvivoRole = nvivomd.tables.get('Role')
    if nvivoRole == None:
        nvivoRole = Table('Role', nvivomd,
            Column('Item1_Id',      UUID(),         nullable=False),
            Column('TypeId',        Integer,        nullable=False),
            Column('Item2_Id',      UUID(),         nullable=False),
            Column('Tag',           Integer))

    nvivoItem = nvivomd.tables.get('Item')
    if nvivoItem == None:
        nvivoItem = Table('Item', nvivomd,
            Column('Id',            UUID(),         nullable=False),
            Column('TypeId',        Integer,        nullable=False),
            Column('Name',          String(256),    nullable=False),
            Column('Description',   String(512),    nullable=False),
            Column('CreatedDate',   DateTime,       nullable=False),
            Column('ModifiedDate',  DateTime,       nullable=False),
            Column('CreatedBy',     UUID(),         nullable=False),
            Column('ModifiedBy',    UUID(),         nullable=False),
            Column('System',        Boolean,        nullable=False),
            Column('ReadOnly',      Boolean,        nullable=False))

    nvivoExtendedItem = nvivomd.tables.get('ExtendedItem')
    if nvivoExtendedItem == None:
        nvivoExtendedItem = Table('Item', nvivomd,
            Column('Item_Id',       UUID(),         nullable=False),
            Column('Properties',    LargeBinary,    nullable=False))

    nvivoCategory = nvivomd.tables.get('Category')
    if nvivoCategory == None:
        nvivoCategory = Table('Item', nvivomd,
            Column('Item_Id',       UUID(),         nullable=False),
            Column('Layout',        LargeBinary,    nullable=False))

    nvivoSource = nvivomd.tables.get('Source')
    if nvivoSource == None:
        nvivoSource = Table('Source', nvivomd,
            Column('Item_Id',       UUID(),         nullable=False),
            Column('TypeId',        Integer,        nullable=False),
#            Column('Object', blob, nullable=False),
            Column('PlainText',     String),
            Column('LengthX',       Integer,        nullable=False),
            Column('LengthY',       Integer))

    nvivoNodeReference = nvivomd.tables.get('NodeReference')
    if nvivoNodeReference == None:
        nvivoNodeReference = Table('NodeReference', nvivomd,
            Column('Id',            UUID(),         nullable=False),
            Column('Node_Item_Id',  UUID(),         nullable=False),
            Column('Source_Item_Id', UUID(),        nullable=False),
            Column('CompoundSourceRegion_Id', UUID()),
            Column('ReferenceTypeId', Integer,      nullable=False),
            Column('StartX',        Integer,        nullable=False),
            Column('LengthX',       Integer,        nullable=False),
            Column('StartY',        Integer),
            Column('LengthY',       Integer),
            Column('CreatedDate',   DateTime,       nullable=False),
            Column('ModifiedDate',  DateTime,       nullable=False),
            Column('CreatedBy',     UUID(),         nullable=False),
            Column('ModifiedBy',    UUID(),         nullable=False))

    nvivoAnnotation = nvivomd.tables.get('Annotation')
    if nvivoAnnotation == None:
        nvivoAnnotation = Table('Annotation', nvivomd,
            Column('Id',            UUID(),         nullable=False),
            Column('Item_Id',       UUID(),         nullable=False),
            Column('CompoundSourceRegion_Id', UUID()),
            Column('Text',          String(1024), nullable=False),
            Column('ReferenceTypeId', Integer,      nullable=False),
            Column('StartX',        Integer,        nullable=False),
            Column('LengthX',       Integer,        nullable=False),
            Column('StartY',        Integer),
            Column('LengthY',       Integer),
            Column('CreatedDate',   DateTime,       nullable=False),
            Column('ModifiedDate',  DateTime,       nullable=False),
            Column('CreatedBy',     UUID(),         nullable=False),
            Column('ModifiedBy',    UUID(),         nullable=False))

    nvivoUserProfile = nvivomd.tables.get('UserProfile')
    if nvivoUserProfile == None:
        nvivoUserProfile = Table('UserProfile', nvivomd,
            Column('Id',            UUID(),         nullable=False),
            Column('Initials',      String(16),   nullable=False),
            Column('AccountName',   String(256)),
            Column('ColorArgb',     Integer))

    nvivomd.create_all(nvivodb)

# Project
    if args.project != 'skip':
        normProject = normmd.tables['Project']
        sel = select([normProject.c.Title,
                      normProject.c.Description,
                      normProject.c.CreatedBy,
                      normProject.c.CreatedDate,
                      normProject.c.ModifiedBy,
                      normProject.c.ModifiedDate])
        projects = [dict(row) for row in normdb.execute(sel)]

        if args.windows:
            for project in projects:
                project['Title']       = ''.join(map(lambda ch: chr(ord(ch) + 0x377), project['Title']))
                project['Description'] = ''.join(map(lambda ch: chr(ord(ch) + 0x377), project['Description']))

        sel = select([nvivoProject.c.Title])
        nvivoprojects = [dict(row) for row in nvivodb.execute(sel)]
        if len(nvivoprojects) == 1:
            nvivodb.execute(nvivoProject.update(), projects)
        else:
            nvivodb.execute(nvivoProject.insert(), projects)

# Node Categories
    if args.node_categories != 'skip':

        # Look up head node category, fudge it if it doesn't exist.
        sel = select([nvivoItem.c.Id])
        sel = sel.where(and_(
            nvivoItem.c.TypeId == literal_column('0'),
            nvivoItem.c.Name == literal_column('\'Node Classifications\'')))
        headnodecategory = nvivodb.execute(sel).fetchone()
        if headnodecategory == None:
            #  Create the magic node category from NVivo's empty project
            headnodecategory = {'Id':'987EFFB2-CC02-469B-9BB3-E345BB8F8362'}

        normNodeCategory = normmd.tables['NodeCategory']
        sel = select([normNodeCategory.c.Id,
                      normNodeCategory.c.Parent,
                      normNodeCategory.c.Name,
                      normNodeCategory.c.Description,
                      normNodeCategory.c.CreatedBy,
                      normNodeCategory.c.CreatedDate,
                      normNodeCategory.c.ModifiedBy,
                      normNodeCategory.c.ModifiedDate])
        nodecategories = [dict(row) for row in normdb.execute(sel)]
        for nodecategory in nodecategories:
            if nodecategory['Id'] == None:
                nodecategory['Id'] = uuid.uuid4()
            if args.windows:
                nodecategory['Name']        = ''.join(map(lambda ch: chr(ord(ch) + 0x377), nodecategory['Name']))
                nodecategory['Description'] = ''.join(map(lambda ch: chr(ord(ch) + 0x377), nodecategory['Description']))
            if nodecategory['Parent'] == None:
                nodecategory['Parent'] = headnodecategory['Id']

        sel = select([nvivoItem.c.Id,
                      nvivoRole.c.Item1_Id,
                      nvivoRole.c.Item2_Id,
                      nvivoRole.c.TypeId])
        sel = sel.where(and_(
                      nvivoItem.c.TypeId   == literal_column('52'),
                      nvivoRole.c.TypeId   == literal_column('0'),
                      nvivoRole.c.Item2_Id == nvivoItem.c.Id))
        if args.node_categories == 'merge':
            sel = sel.where(
                      nvivoItem.c.Id       == bindparam('Id'))

        itemsandroles = [dict(row) for row in nvivodb.execute(sel)]

        if len(itemsandroles) > 0:
            nvivodb.execute(nvivoItem.delete(nvivoItem.c.Id == bindparam('Id')), itemsandroles)
            nvivodb.execute(nvivoRole.delete(and_(
                nvivoRole.c.Item1_Id == bindparam('Item1_Id'),
                nvivoRole.c.TypeId   == literal_column('0'),
                nvivoRole.c.Item2_Id == bindparam('Item2_Id'))), itemsandroles)

        if len(nodecategories) > 0:
            nvivodb.execute(nvivoItem.insert().values({
                        'TypeId':   literal_column('52'),
                        'System':   literal_column('0'),
                        'ReadOnly': literal_column('0')
                }), nodecategories)

            nvivodb.execute(nvivoRole.insert().values({
                        'Item1_Id': bindparam('Parent'),
                        'Item2_Id': bindparam('Id'),
                        'TypeId':   literal_column('0')
                }), nodecategories)
            nvivodb.execute(nvivoExtendedItem.insert().values({
                        'Item_Id': bindparam('Id'),
                        'Properties': literal_column('\'<Properties xmlns="http://qsr.com.au/XMLSchema.xsd"><Property Key="EndNoteReferenceType" Value="-1" /></Properties>\'')
                }), nodecategories)
            nvivodb.execute(nvivoCategory.insert().values({
                        'Item_Id': bindparam('Id'),
                        'Layout' : literal_column('\'<CategoryLayout xmlns="http://qsr.com.au/XMLSchema.xsd"><SortedColumn Ascending="true">-1</SortedColumn><RecordHeaderWidth>100</RecordHeaderWidth><ShowRowIDs>true</ShowRowIDs><ShowColumnIDs>true</ShowColumnIDs><Transposed>false</Transposed><NameSource>1</NameSource><RowsUserOrdered>false</RowsUserOrdered><ColumnsUserOrdered>true</ColumnsUserOrdered></CategoryLayout>\'')
                }), nodecategories)

#Nodes
    if args.nodes != 'skip':
        normNode = normmd.tables['Node']
        sel = select([normNode.c.Id,
                      normNode.c.Category,
                      normNode.c.Name,
                      normNode.c.Description,
                      normNode.c.CreatedBy,
                      normNode.c.CreatedDate,
                      normNode.c.ModifiedBy,
                      normNode.c.ModifiedDate])
        nodes = [dict(row) for row in normdb.execute(sel)]

        nodes = [dict(row) for row in nodes]
        for node in nodes:
            if nodecategory['Id'] == None:
                nodecategory['Id'] = uuid.uuid4()
            if args.windows:
                node['Name']        = ''.join(map(lambda ch: chr(ord(ch) + 0x377), node['Name']))
                node['Description'] = ''.join(map(lambda ch: chr(ord(ch) + 0x377), node['Description']))

        sel = select([nvivoItem.c.Id,
                      nvivoRole.c.Item1_Id,
                      nvivoRole.c.Item2_Id,
                      nvivoRole.c.TypeId])
        if args.node_categories == 'replace':
            sel = sel.where(and_(
                          or_(nvivoItem.c.TypeId == literal_column('16'), nvivoItem.c.TypeId == literal_column('62')),
                          nvivoRole.c.TypeId == literal_column('14'),
                          nvivoRole.c.Item1_Id == nvivoItem.c.Id))
            itemsandroles = [dict(row) for row in nvivodb.execute(sel)]
        elif args.node_categories == 'merge':
            sel = sel.where(and_(
                          nvivoItem.c.Id       == bindparam('Id'),
                          nvivoRole.c.TypeId   == literal_column('14'),
                          nvivoRole.c.Item1_Id == nvivoItem.c.Id))
            itemsandroles = [dict(row) for row in nvivodb.execute(sel, nodecategories)]

        if len(itemsandroles) > 0:
            nvivodb.execute(nvivoItem.delete(nvivoItem.c.Id == bindparam('Id')), itemsandroles)
            nvivodb.execute(nvivoRole.delete(and_(
                nvivoRole.c.Item1_Id == bindparam('Item1_Id'),
                nvivoRole.c.TypeId   == literal_column('0'),
                nvivoRole.c.Item2_Id == bindparam('Item2_Id'))), itemsandroles)

        if len(nodes) > 0:
            nvivodb.execute(nvivoItem.insert().values({
                    'TypeId':   literal_column('16'),
                    'System':   literal_column('0'),
                    'ReadOnly': literal_column('0')
                }), nodes)

            nvivodb.execute(nvivoRole.insert().values({
                    'Item1_Id': bindparam('Id'),
                    'Item2_Id': bindparam('Category'),
                    'TypeId':   literal_column('0')
                }), nodes)

    sys.exit()

# Node attribute values
    if args.node_attributes != 'skip':
        normNodeAttribute = normmd.tables['NodeAttribute']
        sel = select([normNodeAttribute.c.Node,
                      normNodeAttribute.c.Name,
                      normNodeAttribute.c.Value,
                      normNodeAttribute.c.CreatedBy,
                      normNodeAttribute.c.CreatedDate,
                      normNodeAttribute.c.ModifiedBy,
                      normNodeAttribute.c.ModifiedDate])
        nodeattributes = [dict(row) for row in normdb.execute(sel)]

        # Below is some SQL wrangling that gets pretty complicated: five joins in one query
        # is about as much as I can handle.
        nvivoNodeCategoryItem  = nvivoItem.alias(name='NodeCategoryItem')
        nvivoNodeCategoryRole  = nvivoRole.alias(name='NodeCategoryRole')
        nvivoCategoryAttributeItem = nvivoItem.alias(name='CategoryAttributeItem')
        nvivoCategoryAttributeRole = nvivoRole.alias(name='CategoryAttributeRole')
        nvivoAttributeValueItem = nvivoItem.alias(name='AttributeValueItem')
        nvivoAttributeValueRole = nvivoRole.alias(name='AttributeValueRole')
        nvivoNodeValueRole = nvivoRole.alias(name='NodeValueRole')

        categorysel = select([
                nvivoNodeCategoryRole.c.Item2_Id.label('Category'),
                nvivoNodeCategoryItem.c.Name.label('CategoryName')
            ]).where(and_(
                nvivoNodeCategoryRole.c.TypeId   == literal_column('14'),
                nvivoNodeCategoryRole.c.Item1_Id == bindparam('Node'),
                nvivoNodeCategoryItem.c.Id == nvivoNodeCategoryRole.c.Item2_Id
            ))
        attributeselect = select([
                nvivoCategoryAttributeRole.c.Item1_Id.label("AttributeId"),
                nvivoCategoryAttributeRole.c.TypeId.label("TypeId1"),
                nvivoCategoryAttributeRole.c.Item2_Id.label("Category1")
            ])
        attributenamejoin = attributeselect.join(
                nvivoCategoryAttributeItem,
                nvivoCategoryAttributeItem.c.Id == attributeselect.c.AttributeId
            )
        categoryjoin = categorysel.outerjoin(
                attributenamejoin,
                and_(
                    attributeselect.c.TypeId1   == literal_column('13'),
                    attributeselect.c.Category1 == categorysel.c.Category,
                    nvivoCategoryAttributeItem.c.Id == attributeselect.c.AttributeId,
                    nvivoCategoryAttributeItem.c.Name == bindparam('Name')
            ))

        valueselect = select([
                nvivoAttributeValueRole.c.Item2_Id.label("ValueId"),
                nvivoAttributeValueRole.c.TypeId.label("TypeId2"),
                nvivoAttributeValueRole.c.Item1_Id.label("Attribute1")
            ])
        nodevaluejoin = valueselect.join(
                nvivoNodeValueRole,
                and_(
                    nvivoNodeValueRole.c.TypeId == literal_column('7'),
                    nvivoNodeValueRole.c.Item2_Id == valueselect.c.ValueId,
                    # I can't figure out why using
                    # 'nvivoNodeValueRole.c.Item1_Id == categorysel.c.Node' instead
                    # of another bound parameter doesn't work here, so if anyone else can
                    # please let me know.
                    nvivoNodeValueRole.c.Item1_Id == bindparam('Node')
            ))
        valuenamejoin = nodevaluejoin.join(
                nvivoAttributeValueItem,
                nvivoAttributeValueItem.c.Id == nodevaluejoin.c.ValueId
            )
        valuejoin = categoryjoin.outerjoin(
                valuenamejoin,
                and_(
                    valueselect.c.TypeId2 == literal_column('6'),
                    valueselect.c.Attribute1 == attributeselect.c.AttributeId,
                    nvivoAttributeValueItem.c.Id == valueselect.c.ValueId
            ))

        finalsel = select([
                valuejoin.c.Category,
                valuejoin.c.CategoryName,
                valuejoin.c.AttributeId,
                nvivoCategoryAttributeItem.c.Name.label('AttributeName'),
                valuejoin.c.ValueId,
                nvivoAttributeValueItem.c.Name.label('Value')]
            ).select_from(valuejoin)

        for nodeattribute in nodeattributes:
            if args.windows:
                nodeattribute['Name']  = ''.join(map(lambda ch: chr(ord(ch) + 0x377), nodeattribute['Name']))
                nodeattribute['Value'] = ''.join(map(lambda ch: chr(ord(ch) + 0x377), nodeattribute['Value']))



            existingattributes = [dict(row) for row in nvivodb.execute(finalsel, nodeattribute)]
            if len(existingattributes) == 0:
                print ("Node attribute: " + nodeattribute['Name'] + " needs definition.")
            elif len(existingattributes) == 1:
                for existingattribute in existingattributes:
                    if existingattribute['Value'] == None:
                        print ("Node attribute: " + nodeattribute['Name'] + " undefined.")
                    elif existingattribute['Value'] != nodeattribute['Value']:
                        print ("Node attribute: " + nodeattribute['Name'] + " defined.")

            #nodeattribute['nameuuid']  = str(uuid.uuid4()).lower()
            #nodeattribute['valueuuid'] = str(uuid.uuid4()).lower()

        #nvivoNodeItem  = nvivoItem.alias(name='NodeItem')
        #nvivoNameItem  = nvivoItem.alias(name='NameItem')
        #nvivoNameRole  = nvivoRole.alias(name='NameRole')
        #nvivoValueItem = nvivoItem.alias(name='ValueItem')
        #nvivoValueRole = nvivoRole.alias(name='ValueRole')
        #sel = select([nvivoNodeItem.c.Id.label('Node'),
                      #nvivoNameItem.c.Name.label('Name'),
                      #nvivoValueItem.c.Name.label('Value'),
                      #nvivoNameRole.c.TypeId.label('NameRoleTypeId'),
                      #nvivoValueRole.c.TypeId.label('ValueRoleTypeId')])
        #sel = sel.where(and_(
                      #or_(nvivoNodeItem.c.TypeId == column('16'), nvivoNodeItem.c.TypeId==column('62')),
                      #nvivoNodeItem.c.Id         == nvivoValueRole.c.Item1_Id,
                      #nvivoValueRole.c.TypeId    == column('7'),
                      #nvivoValueItem.c.Id        == nvivoValueRole.c.Item2_Id,
                      #nvivoNameRole.c.Item2_Id   == nvivoValueRole.c.Item2_Id,
                      #nvivoNameRole.c.TypeId     == column('6'),
                      #nvivoNameItem.c.Id         == nvivoNameRole.c.Item1_Id)))
        #if args.node_categories == 'merge':
            #sel = sel.where(and_(
                      #nvivoNodeItem.c.Id         == bindparam('Node'),
                      #nvivoNameItem.c.Name       == bindparam('Name'),
                      #nvivoNameItem.c.Value      == bindparam('Value')))

        #itemsandroles = [dict(row) for row in nvivodb.execute(sel), nodecategories]

        #if len(itemsandroles) > 0:
            #nvivodb.execute(nvivoItem.delete(nvivoItem.c.Id == bindparam('Name')), itemsandroles)
            #nvivodb.execute(nvivoRole.delete(and_(
                #nvivoRole.c.Item1_Id == bindparam('Item1_Id'),
                #nvivoRole.c.TypeId   == column('0'),
                #nvivoRole.c.Item2_Id == bindparam('Item2_Id'))), itemsandroles)

        #if len(nodeattributes) > 0:
            ## Name item
            #nvivodb.execute(nvivoItem.insert().values({
                    #'Id':           bindparam('nameuuid'),
                    #'TypeId':       column('20'),
                    #'Description':  column('\"\"'),
                    #'System':       column('0'),
                    #'ReadOnly':     column('0')
                #}), nodeattributes)

            ## Value item
            #nvivodb.execute(nvivoItem.insert().values({
                    #'Id':           bindparam('valueuuid'),
                    #'TypeId':       column('21'),
                    #'Description':  column('\"\"'),
                    #'Tag':          column('0'),  # This should be ordinal of node attribute value
                    #'System':       column('0'),
                    #'ReadOnly':     column('0')
                #}), nodeattributes)

            ## Name role
            #nvivodb.execute(nvivoRole.insert().values({
                    #'Item1_Id':     bindparam('nameuuid'),
                    #'Item2_Id':     bindparam('valueuuid'),
                    #'TypeId':       column('6')
                #}), nodeattributes)

# Source categories

    sourcecategories = norm.execute ('''
                    SELECT
                        Id,
                        Parent,
                        Name,
                        Description,
                        CreatedBy,
                        CreatedDate,
                        ModifiedBy,
                        ModifiedDate
                    FROM
                        SourceCategory
                ''')

    if args.windows:
        sourcecategories = [dict(row) for row in sourcecategories]
        for sourcecategory in sourcecategories:
            sourcecategory['Name']        = ''.join(map(lambda ch: chr(ord(ch) + 0x377), sourcecategory['Name']))
            sourcecategory['Description'] = ''.join(map(lambda ch: chr(ord(ch) + 0x377), sourcecategory['Description']))

    for sourcecategory in sourcecategories:
        # Item
        nvivo.execute ('''
                    INSERT INTO
                        Item
                    (
                        Id,
                        TypeId,
                        Name,
                        Description,
                        CreatedBy,
                        CreatedDate,
                        ModifiedBy,
                        ModifiedDate
                    ) VALUES (
                        :Id,
                        51,
                        :Name,
                        :Description,
                        :CreatedBy,
                        :CreatedDate,
                        :ModifiedBy,
                        :ModifiedDate
                    )
                ''',
                    {
                        'Id':sourcecategory['Id'],
                        'Name':sourcecategory['Name'],
                        'Description':sourcecategory['Description'],
                        'CreatedBy':sourcecategory['CreatedBy'],
                        'CreatedDate':sourcecategory['CreatedDate'],
                        'ModifiedBy':sourcecategory['ModifiedBy'],
                        'ModifiedDate':sourcecategory['ModifiedDate']
                    }
            )
        if sourcecategory['Parent'] != None:
            parentsourcecategory = next(index for index in sourcecategories if index['Id'] == sourcecategory['Parent'])
            nvivo.execute ('''
                    INSERT INTO
                        Role
                    (
                        Item1_Id,
                        TypeId,
                        Item2_Id,
                        Tag
                    ) VALUES (
                        :Item1_Id,
                        0,
                        :Item2_Id,
                        0
                    )
                    ''',
                    {
                        'Item1_Id':parentsourcecategory['Id'],
                        'Item2_Id':sourcecategory['Id']
                    }
                )

# Sources

    sources = norm.execute('''
                    SELECT
                        Id,
                        Category,
                        Name,
                        Description,
                        Content,
                        CreatedBy,
                        CreatedDate,
                        ModifiedBy,
                        ModifiedDate
                    FROM
                        Source
        ''')

    if args.windows:
        sources = [dict(row) for row in sources]
        for source in sources:
            source['Name']        = ''.join(map(lambda ch: chr(ord(ch) + 0x377), source['Name']))
            source['Description'] = ''.join(map(lambda ch: chr(ord(ch) + 0x377), source['Description']))

    nvivo.executemany ('''
                    INSERT INTO
                        Source
                    (
                        Item_Id,
                        TypeId,
                        PlainText,
                        LengthX,
                        LengthY
                    ) VALUES (
                        :Id,
                        0,
                        REPLACE(:Content, "''' + os.linesep * int(2 / len(os.linesep)) + '''", "\\n"),
                        0,
                        NULL
                    )
        ''', sources)

    for source in sources:
        # Source item
        nvivo.execute ('''
                    INSERT INTO
                        Item
                    (
                        Id,
                        TypeId,
                        Name,
                        Description,
                        CreatedBy,
                        CreatedDate,
                        ModifiedBy,
                        ModifiedDate
                    ) VALUES (
                        :Id,
                        2,
                        :Name,
                        :Description,
                        :CreatedBy,
                        :CreatedDate,
                        :ModifiedBy,
                        :ModifiedDate
                    )
                ''',
                    {
                        'Id':source['Id'],
                        'Name':source['Name'],
                        'Description':source['Description'],
                        'CreatedBy':source['CreatedBy'],
                        'CreatedDate':source['CreatedDate'],
                        'ModifiedBy':source['ModifiedBy'],
                        'ModifiedDate':source['ModifiedDate']
                    }
            )
        # Source category role
        nvivo.execute ('''
                    INSERT INTO
                        Role
                    (
                        Item1_Id,
                        TypeId,
                        Item2_Id,
                        Tag
                    ) VALUES (
                        :Item1_Id,
                        14,
                        :Item2_Id,
                        0
                    )
                ''',
                    {
                        'Item1_Id':source['Id'],
                        'Item2_Id':source['Category']
                    }
            )

# Source attribute values

    sourceattrs = norm.execute ('''
                    SELECT
                        Source,
                        Name,
                        Value,
                        CreatedBy,
                        CreatedDate,
                        ModifiedBy,
                        ModifiedDate
                    FROM
                        SourceAttribute
        ''')

    if args.windows:
        sourceattrs = [dict(row) for row in sourceattrs]
        for sourceattr in sourceattrs:
            sourceattr['Name']  = ''.join(map(lambda ch: chr(ord(ch) + 0x377), sourceattr['Name']))
            sourceattr['Value'] = ''.join(map(lambda ch: chr(ord(ch) + 0x377), sourceattr['Value']))

    for sourceattr in sourceattrs:
        nameuuid  = str(uuid.uuid4()).lower()
        valueuuid = str(uuid.uuid4()).lower()

        # Name item
        nvivo.execute ('''
                    INSERT INTO
                        Item
                    (
                        Id,
                        TypeId,
                        Name,
                        Description,
                        CreatedBy,
                        CreatedDate,
                        ModifiedBy,
                        ModifiedDate
                    ) VALUES (
                        :Id,
                        20,
                        :Name,
                        '',
                        :CreatedBy,
                        :CreatedDate,
                        :ModifiedBy,
                        :ModifiedDate
                    )
                ''',
                    {
                        'Id':nameuuid,
                        'Name':sourceattr['Name'],
                        'CreatedBy':sourceattr['CreatedBy'],
                        'CreatedDate':sourceattr['CreatedDate'],
                        'ModifiedBy':sourceattr['ModifiedBy'],
                        'ModifiedDate':sourceattr['ModifiedDate']
                    }
            )
        # Value item
        nvivo.execute ('''
                    INSERT INTO
                        Item
                    (
                        Id,
                        TypeId,
                        Name,
                        Description,
                        CreatedBy,
                        CreatedDate,
                        ModifiedBy,
                        ModifiedDate
                    ) VALUES (
                        :Id,
                        21,
                        :Name,
                        '',
                        :CreatedBy,
                        :CreatedDate,
                        :ModifiedBy,
                        :ModifiedDate
                    )
                ''',
                    {
                        'Id':valueuuid,
                        'Name':sourceattr['Value'],
                        'CreatedBy':sourceattr['CreatedBy'],
                        'CreatedDate':sourceattr['CreatedDate'],
                        'ModifiedBy':sourceattr['ModifiedBy'],
                        'ModifiedDate':sourceattr['ModifiedDate']
                    }
            )
        # Name role
        nvivo.execute ('''
                    INSERT INTO
                        Role
                    (
                        Item1_Id,
                        TypeId,
                        Item2_Id,
                        Tag
                    ) VALUES (
                        :Item1_Id,
                        6,
                        :Item2_Id,
                        0
                    )
                ''',
                    {
                        'Item1_Id':nameuuid,
                        'Item2_Id':valueuuid
                    }
            )
        # Value role
        nvivo.execute ('''
                    INSERT INTO
                        Role
                    (
                        Item1_Id,
                        TypeId,
                        Item2_Id,
                        Tag
                    ) VALUES (
                        :Item1_Id,
                        7,
                        :Item2_Id,
                        0
                    )
                ''',
                    {
                        'Item1_Id':sourceattr['Source'],
                        'Item2_Id':valueuuid
                    }
            )

# Tagging and annotations

    taggings = norm.execute('''
                    SELECT
                        Source,
                        Node,
                        Memo,
                        Fragment,
                        CreatedBy,
                        CreatedDate,
                        ModifiedBy,
                        ModifiedDate
                    FROM
                        Tagging
        ''')

    for tagging in taggings:
        matchfragment = re.match("([0-9]+):([0-9]+)", tagging['Fragment'])
        startX = int(matchfragment.group(1))
        endX = int(matchfragment.group(2))
        lengthX = endX - startX + 1

        annotationuuid  = str(uuid.uuid4()).lower() # Not clear what purpose this field serves

        # If no node then this is what NVivo calls an annotation
        if tagging['Node'] == None:
            nvivo.execute ('''
                    INSERT INTO
                        Annotation
                    (
                        Id,
                        Item_Id,
                        Text,
                        ReferenceTypeId,
                        StartX,
                        LengthX,
                        StartY,
                        LengthY,
                        CreatedBy,
                        CreatedDate,
                        ModifiedBy,
                        ModifiedDate
                    ) VALUES (
                        :Id,
                        :Item1_Id,
                        :Memo,
                        0,
                        :StartX,
                        :LengthX,
                        0,
                        0,
                        :CreatedBy,
                        :CreatedDate,
                        :ModifiedBy,
                        :ModifiedDate
                    )
                    ''',
                    {
                        'Id':annotationuuid,
                        'Item1_Id':tagging['Source'],
                        'Memo':tagging['Memo'],
                        'StartX':startX,
                        'LengthX':lengthX,
                        'CreatedBy':tagging['CreatedBy'],
                        'CreatedDate':tagging['CreatedDate'],
                        'ModifiedBy':tagging['ModifiedBy'],
                        'ModifiedDate':tagging['ModifiedDate']
                    }
                )
        # Otherwise this is a tagging and memo will be lost.
        else:
            nvivo.execute ('''
                    INSERT INTO
                        NodeReference
                    (
                        Id,
                        Node_Item_Id,
                        Source_Item_Id,
                        ReferenceTypeId,
                        StartX,
                        LengthX,
                        StartY,
                        LengthY,
                        CreatedBy,
                        CreatedDate,
                        ModifiedBy,
                        ModifiedDate
                    ) VALUES (
                        :Id,
                        :Node_Item_Id,
                        :Source_Item_Id,
                        0,
                        :StartX,
                        :LengthX,
                        0,
                        0,
                        :CreatedBy,
                        :CreatedDate,
                        :ModifiedBy,
                        :ModifiedDate
                    )
                    ''',
                    {
                        'Id':annotationuuid,
                        'Node_Item_Id':tagging['Node'],
                        'Source_Item_Id':tagging['Source'],
                        'StartX':startX,
                        'LengthX':lengthX,
                        'CreatedBy':tagging['CreatedBy'],
                        'CreatedDate':tagging['CreatedDate'],
                        'ModifiedBy':tagging['ModifiedBy'],
                        'ModifiedDate':tagging['ModifiedDate']
                    }
                )

    # Users
    users = norm.execute('''
                    SELECT
                        Id,
                        Name
                    FROM
                        User
                                         ''')

    for user in users:
        nvivo.execute ('''
                    INSERT INTO
                        UserProfile
                    (
                        Id,
                        Initials,
                        Name
                    ) VALUES (
                        :Id,
                        :Initials,
                        :Name
                    )
                    ''',
                    {
                        'Id':user['Id'],
                        'Initials':''.join(partname[0].upper() for partname in user['Name'].split()),
                        'Name':user['Name']
                    }
                )

# All done.

except exc.SQLAlchemyError:
    raise