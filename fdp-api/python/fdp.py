# FAIR Data Point
#
# Copyright 2015 Netherlands eScience Center in collaboration with
# Dutch Techcenter for Life Sciences.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
# FAIR Data Point (FDP) exposes the following endpoints (URL paths):
#   [ /, /doc, /doc/ ]   = Redirects to the API documentation
#   /fdp                 = Returns FDP metadata
#   /catalog/{catalogID} = Returns catalog metadata (default: catalog-01)
#   /dataset/{datasetID} = Returns dataset metadata (default: breedb)
#   /distribution/{distributionID} = Returns distribution metadata
#                                    (default: breedb-sparql)
#
# This services makes use of:
#   Data Catalog Vocabulary, http://www.w3.org/TR/vocab-dcat/
#   Dublin Core Metadata Terms, http://dublincore.org/documents/dcmi-terms/
#   DBpedia, http://dbpedia.org/resource/)
#

__author__ = 'Arnold Kuzniar'
__version__ = '0.5.0'
__status__ = 'beta'
__license__ = 'Apache License, Version 2.0'


from bottle import get, run, static_file, redirect, response, request, opt, \
    install
from metadata import FAIRConfigReader, FAIRGraph, FDPath
from datetime import datetime
from functools import wraps
from logging import getLogger, FileHandler, INFO


# log HTTP requests
logger = getLogger(__name__)
logger.setLevel(INFO)
fh = FileHandler('access.log')
fh.setLevel(INFO)
logger.addHandler(fh)


def logHttpRequests(fn):
    """Log HTTP requests into log file using Common Log Format"""
    @wraps(fn)
    def _log_to_logger(*args, **kwargs):
        request_time = datetime.now().strftime("%d/%b/%Y %H:%M:%S")
        logger.info('%s - - [%s] "%s %s %s" %d' % (
            request.remote_addr,
            request_time,
            request.method,
            request.urlparts.path,
            request.get('SERVER_PROTOCOL'),
            response.status_code))
        return fn(*args, **kwargs)
    return _log_to_logger


install(logHttpRequests)

# populate FAIR metadata from config file
reader = FAIRConfigReader()
scheme = 'http'
host = opt.bind  # pass host:[port] through the command-line -b option
base_uri = '{}://{}'.format(scheme, host)
g = FAIRGraph(base_uri)

for triple in reader.getTriples():
    g.setMetadata(triple)


def httpResponse(graph, uri):
    """HTTP response: FAIR metadata in RDF and JSON-LD formats"""
    accept_header = request.headers.get('Accept')
    fmt = 'turtle'  # default RDF serialization
    mime_types = {
        'text/turtle': 'turtle',
        'application/rdf+xml': 'xml',
        'application/ld+json': 'json-ld',
        'application/n-triples': 'nt'
    }

    if accept_header in mime_types:
        fmt = mime_types[accept_header]

    serialized_graph = graph.serialize(uri, fmt)

    if serialized_graph is None:
        response.status = 404  # web resource not found
        return

    response.content_type = 'text/plain'
    response.set_header('Allow', 'GET')

    return serialized_graph


# HTTP request handlers
@get(['/', '/doc', '/doc/'])
def defaultPage():
    redirect('/doc/index.html')


@get(FDPath('doc', '<fname:path>'))
def sourceDocFiles(fname):
    return static_file(fname, root='doc')


@get(FDPath('fdp'))
def getFdpMetadata(graph=g):
    return httpResponse(graph, graph.fdpURI())


@get(FDPath('cat', '<catalog_id>'))
def getCatalogMetadata(catalog_id, graph=g):
    return httpResponse(graph, graph.catURI(catalog_id))


@get(FDPath('dat', '<dataset_id>'))
def getDatasetMetadata(dataset_id, graph=g):
    return httpResponse(graph, graph.datURI(dataset_id))


@get(FDPath('dist', '<distribution_id>'))
def getDistributionMetadata(distribution_id, graph=g):
    return httpResponse(graph, graph.distURI(distribution_id))


if __name__ == '__main__':
    run(server='wsgiref')
