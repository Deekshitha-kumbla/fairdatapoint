from os import path
from rdflib import ConjunctiveGraph, URIRef, Literal
from rdflib.namespace import Namespace, RDF, RDFS, DCTERMS, XSD
from rdflib.plugin import register, Serializer
from ConfigParser import SafeConfigParser
from datetime import datetime
from urllib2 import urlparse


# rdflib-jsonld module required
register('application/ld+json', Serializer, 'rdflib_jsonld.serializer', 'JsonLDSerializer')

# default metadata config file
_CONFIG_FILE = path.join(path.dirname(__file__), 'metadata.ini')

# define additional namespaces
DCAT = Namespace('http://www.w3.org/ns/dcat#')
LANG = Namespace('http://id.loc.gov/vocabulary/iso639-1/')
DBPEDIA = Namespace('http://dbpedia.org/resource/')
#SPARQLSD = Namespace('http://www.w3.org/ns/sparql-service-description#')

# define which sections/fields in the metadata config file are mandatory
_CORE_META   = ['title','publisher','version','issued','modified']
_REQUIRED_META = dict(fdp          = _CORE_META + ['fdp_id','catalog_id'],
                      catalog      = _CORE_META + ['dataset_id','theme_taxonomy'],
                      dataset      = _CORE_META + ['distribution_id','theme'],
                      distribution = _CORE_META + ['access_url|download_url','media_type','license'])

# mappings between fields in the config file and ontologies/vocabularies and data types
_ONTO_MAP = dict(fdp_id          = [ ( DCTERMS.identifier, XSD.string ) ],
                 catalog_id      = [ ( DCTERMS.hasPart, XSD.anyURI ),
                                     ( RDFS.seeAlso, XSD.anyURI ) ],
                 dataset_id      = [ ( DCAT.dataset, XSD.anyURI ),
                                     ( RDFS.seeAlso, XSD.anyURI ) ],
                 distribution_id = [ ( DCAT.distribution, XSD.anyURI ), 
                                     ( RDFS.seeAlso, XSD.anyURI ) ],
                 title           = [ ( DCTERMS.title, XSD.string ),
                                     ( RDFS.label, XSD.string ) ],
                 description     = [ ( DCTERMS.description, XSD.string ) ],
                 publisher       = [ ( DCTERMS.publisher, XSD.anyURI ) ],
                 issued          = [ ( DCTERMS.issued, XSD.date ) ],
                 modified        = [ ( DCTERMS.modified, XSD.date ) ],
                 version         = [ ( DCTERMS.version, XSD.string ) ],
                 license         = [ ( DCTERMS.license, XSD.anyURI ) ],
                 theme           = [ ( DCAT.theme, XSD.anyURI ) ],
                 theme_taxonomy  = [ ( DCAT.themeTaxonomy, XSD.anyURI ) ],
                 landing_page    = [ ( DCAT.landingPage, XSD.anyURI ) ],
                 keyword         = [ ( DCAT.keyword, XSD.string ) ],
                 access_url      = [ ( DCAT.accessURL, XSD.anyURI ) ],
                 download_url    = [ ( DCAT.downloadURL, XSD.anyURI ) ],
                 media_type      = [ ( DCAT.mediaType, XSD.string ) ] )

# paths (endpoints) available through FDP
_RESOURCE_PATH = dict(fdp  = '/fdp',
                      doc  = '/doc',
                      cat  = '/catalog',
                      dat  = '/dataset',
                      dist = '/distribution')


def _errorSectionNotFound(section):
   return "Section '%s' not found." % section


def _errorFieldNotFound(field):
   return "Field '%s' not found." % field


def _errorFieldInSectionNotFound(field, section):
   return "Field '%s' not found in section '%s'." % (field, section)


def _errorResourceNotFound(resource):
   return "Resource '%s' not found." % resource


def _errorResourceIdNotUnique(id):
   return "Resource ID '%s' must be unique." % id


def _errorSectionNotReferenced(section, field, ref_section_by_field):
   return "{f}(s) in the '{s}' section is not referenced in the '{r}/<{f}>' section header(s) or vice versa.".format(f=field, r=ref_section_by_field, s=section)


def mandatoryFields(section):
   assert(section in _REQUIRED_META), _errorSectionNotFound(section)
   return _REQUIRED_META[section]


def mapFieldToOnto(field):
   assert(field in _ONTO_MAP), _errorFieldNotFound(field)
   return _ONTO_MAP[field]


def FDPath(resource, var=None):
   assert(resource in _RESOURCE_PATH), _errorResourceNotFound(resource)
   path = _RESOURCE_PATH[resource]
   var = '' if var is None else '/%s' % str(var)
   
   return path + var


class FAIRConfigReader(object):
   def __init__(self, fname=_CONFIG_FILE):
      parser = SafeConfigParser()
      self._parser = parser
      self._metadata = dict()
      self._readFile(fname)


   def _readFile(self, fname):
      if path.isfile(fname) is False:
         raise IOError('%s config file does not exist.' % fname)

      self._parser.read(fname)

      for section in self._parser.sections():
         self._metadata[section] = dict()

         for field,value in self._parser.items(section):
            if '\n' in value:
               value = value.split('\n')
            self._metadata[section][field] = value

      self._validateParsedMetadata()


   def getMetadata(self):
      return self._metadata


   def getSectionHeaders(self):
      return self.getMetadata().keys()


   def getFields(self, section):
      return self._metadata[section]


   def getItems(self, section, field):
      items = self._metadata[section][field]

      if isinstance(items, list):
         for item in items:
            yield item
      else:
         item = items
         yield item


   def getTriples(self):
      for section,fields in self.getMetadata().iteritems():
         for field in fields:
            for item in self.getItems(section, field):
               yield (section, field, item)


   def _validateParsedMetadata(self):
      section_headers = self.getSectionHeaders()
      sections = dict((section,[]) for section in _REQUIRED_META.keys())
      uniq_resource_ids = dict()

      sfx = '_id'
      fdp, cat, dat, dist = 'fdp', 'catalog', 'dataset', 'distribution'
      fdp_id, cat_id, dat_id, dist_id = fdp + sfx, cat + sfx, dat + sfx, dist + sfx

      # check mandatory sections
      for sh in section_headers:
         if sh in sections:
            sections[sh] = True

         if '/' in sh:
            section, resource_id = sh.split('/')
            if section in sections:
               sections[section].append(resource_id)

      for section,resource in sections.items():
         assert(resource), _errorSectionNotFound(section)

      # check mandatory fields and referenced sections
      for section in section_headers:
         for field in mandatoryFields(section.split('/')[0]):
            fields = self.getFields(section)

            if '|' in field: # distribution has two alternatives: access_url|download_url
               a, b = field.split('|')
               assert(a in fields or b in fields), _errorFieldInSectionNotFound(field, section)
            else:
               assert(field in fields), _errorFieldInSectionNotFound(field, section)

            # resource IDs must be unique
            if field in [fdp_id]:#, cat_id, dat_id, dist_id]:
               for resource_id in self.getItems(section, field):
                  assert(resource_id not in uniq_resource_ids), _errorResourceIdNotUnique(resource_id)
                  uniq_resource_ids[resource_id] = None

         if fdp in section:
            ids_1 = sections[cat]
            ids_2 = [ id for id in self.getItems(section, cat_id) ]
            assert(ids_1 == ids_2), _errorSectionNotReferenced(fdp, cat_id, cat)

         if cat in section:
            ids_1 = sections[dat]
            ids_2 = [ id for id in self.getItems(section, dat_id) ]
            assert(ids_1 == ids_2), _errorSectionNotReferenced(cat, dat_id, dat)

         if dat in section:
            ids_1 = sections[dist]
            ids_2 = [ id for id in self.getItems(section, dist_id) ]
            assert(ids_1 == ids_2), _errorSectionNotReferenced(dat, dist_id, dist)


class FAIRGraph(object):
   def __init__(self, base_uri):
      graph = ConjunctiveGraph()
      self._graph = graph
      self._base_uri = self._validateURI(base_uri)
      self._uniq_ids = dict()

      # bind prefixes to namespaces
      graph.bind('dbp', DBPEDIA)
      graph.bind('dct', DCTERMS)
      graph.bind('dcat', DCAT)
      graph.bind('lang', LANG)
      #graph.bind('sd', SPARQLSD)


   def _validateURI(self, uri):
      u = urlparse.urlparse(uri)

      if u.scheme not in ('http', 'https', 'ftp'):
         raise ValueError("Missing/invalid URI scheme '%s' [http|https|ftp]." % uri)
      
      if u.netloc == '':
         raise ValueError('No host specified.')

      return uri


   def _validateDate(self, date):
      try:
         datetime.strptime(date, "%Y-%m-%d")
      except ValueError:
         raise ValueError("Incorrect date format '%s' [YYYY-MM-DD]." % date)
      else:
         return date


   def baseURI(self):
      return self._base_uri


   def URI(self, resource, id=None):
      return self.baseURI() + FDPath(resource, id)


   def docURI(self):
      return self.URI('doc')


   def fdpURI(self):
      return self.URI('fdp')


   def catURI(self, id):
      return self.URI('cat', id)


   def datURI(self, id):
      return self.URI('dat', id)


   def distURI(self, id):
      return self.URI('dist', id)


   def serialize(self, uri, mime_type):
      if len(self._graphContext(uri).all_nodes()) > 0:
         return self._graphContext(uri).serialize(format=mime_type)


   def setMetadata(self, triple):
      assert(isinstance(triple, tuple) and len(triple) == 3), 'Input must be a triple (s, p, o).'

      s, p, o = triple
      arr = s.split('/')
      resource = arr[0]
      resource_id = arr[1] if len(arr) == 2 else None

      # set FDP metadata
      if resource == 'fdp':
         s = URIRef(self.fdpURI())
         g = self._graphContext(s)

         g.add( (s, RDF.type, DCTERMS.Agent) )
         g.add( (s, DCTERMS.language, LANG.en) )

         for triple in self._mapTriple( (s, p, o) ):
            g.add(triple)

      # set Catalog metadata
      if resource == 'catalog':
         s = URIRef(self.catURI(resource_id))
         g = self._graphContext(s)

         g.add( (s, RDF.type, DCAT.Catalog) )
         g.add( (s, DCTERMS.language, LANG.en) )
         g.add( (s, DCTERMS.identifier, Literal(resource_id, datatype=XSD.string)) )

         for triple in self._mapTriple( (s, p, o) ):
            g.add(triple)

      # set Dataset metadata
      if resource == 'dataset':
         s = URIRef(self.datURI(resource_id))
         g = self._graphContext(s)

         g.add( (s, RDF.type, DCAT.Dataset) )
         g.add( (s, DCTERMS.language, LANG.en) )
         g.add( (s, DCTERMS.identifier, Literal(resource_id, datatype=XSD.string)) )

         for triple in self._mapTriple( (s, p, o) ):
            g.add(triple)

      # set Distribution metadata
      if resource == 'distribution':
         s = URIRef(self.distURI(resource_id))
         g = self._graphContext(s)

         g.add( (s, RDF.type, DCAT.Distribution) )
         g.add( (s, DCTERMS.language, LANG.en) )
         g.add( (s, DCTERMS.identifier, Literal(resource_id, datatype=XSD.string)) )

         for triple in self._mapTriple( (s, p, o) ):
            g.add(triple)


   def _graphContext(self, uri):
      return self._graph.get_context(uri)


   def _mapTriple(self, triple):
      assert(isinstance(triple, tuple) and len(triple) == 3), 'Input must be a triple (s, p, o).'

      s, p, o = triple

      for (mp, dtype) in mapFieldToOnto(p):
         mo = o

         if 'catalog_id' in p:
            mo = self.catURI(o)

         if 'dataset_id' in p:
            mo = self.datURI(o)

         if 'distribution_id' in p:
            mo = self.distURI(o)


         if dtype == XSD.anyURI:
            mo = URIRef(self._validateURI(mo))

         elif dtype == XSD.date:
            mo = Literal(self._validateDate(mo), datatype=dtype)

         else:
            mo = Literal(mo, datatype=dtype)

         yield (s, mp, mo)

