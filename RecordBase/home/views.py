from django.shortcuts import render
from django.http import HttpResponseRedirect, HttpResponse

from SPARQLWrapper import SPARQLWrapper, JSON
from SPARQLWrapper.Wrapper import EndPointInternalError

from rdflib import URIRef, BNode, Literal, Namespace, Graph

import musicbrainzngs
import requests
from requests.exceptions import HTTPError

import sys

musicbrainzngs.set_useragent("ProjectTest/1.0", "( me@example.com )")

dbpedia = SPARQLWrapper("http://live.dbpedia.org/sparql")
dbtune = SPARQLWrapper("http://dbtune.org/musicbrainz/sparql")
bbcmusic = SPARQLWrapper("http://lod.openlinksw.com/sparql/")

BPI_certifications = ["Platinum","Gold","Silver"]

prefixes = """
	PREFIX owl:	<http://www.w3.org/2002/07/owl#>
	PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
	PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
	PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
	PREFIX foaf: <http://xmlns.com/foaf/0.1/>
	PREFIX dc: <http://purl.org/dc/elements/1.1/>
	PREFIX mo: <http://purl.org/ontology/mo/>
	PREFIX rev: <http://purl.org/stuff/rev#>
	PREFIX : <http://dbpedia.org/resource/>
	PREFIX dbp: <http://dbpedia.org/property/>
	PREFIX dbo: <http://dbpedia.org/ontology/>
	PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
	"""

def home(request):
	return render(request, 'home/home.html')

def search(request,query_type,query):
	artist_results = []
	album_results = []

	if query_type == 'artist':
		data = musicbrainzngs.search_artists(query)

		for artist in data['artist-list']:
			artist_results.append([artist['name'], artist['id'], artist.get('disambiguation')])

	elif query_type == 'album':
		data = musicbrainzngs.search_release_groups(query)		

		#def get_album_artists(credits):
			#if len(credits) > 1:
				#artists = []
				#for item in credits:
				#	artists.append(item['artist']['name'])

				#return artists
			#else:
			#return credits[0]['artist']['name']

		for album in data['release-group-list']:
			album_results.append([album['title'], album['id'],album['artist-credit'][0]['artist']['name']])

	return render(request, 'home/home.html', {'artist_list': artist_results, 'album_list': album_results})

def sparql_query(site,select,topic,relationship):
	global dbpedia
	global dbtune
	global bbcmusic
	global prefixes		

	site.setQuery("""
		%s

		SELECT ?%s WHERE {
		<http://dbpedia.org/resource/%s> %s ?%s.
		filter langMatches(lang(?%s),"en") }

	""" % (prefixes,select,topic.replace(" ","_"),relationship,select,select))

	site.setReturnFormat(JSON)
	results = site.query().convert()

	return results

def get_description(topic):
	description = ""

	results = sparql_query(dbpedia,'abstract',topic,'dbo:abstract')

	for result in results["results"]["bindings"]:
		description = result["abstract"]["value"]

	return description

def get_tags(data):
	if 'tag-list' in data:
		sorted_tags = sorted(data['tag-list'], key=lambda x: int(x['count']), reverse=True)
		tags = []

		for tag in sorted_tags:
			tags.append([tag['name'].title(),tag['name'].replace(" ","_")])

		return tags[:5]

def get_dbpedia_genres(resource):
	global dbpedia
	global prefixes
	genres = []

	dbpedia.setQuery("""
		%s

		SELECT ?label WHERE {
		<%s> dbo:genre ?genre.
		?genre rdfs:label ?label.
		filter langMatches(lang(?label),"en") }

	""" % (prefixes,resource)	)

	dbpedia.setReturnFormat(JSON)
	results = dbpedia.query().convert()

	for result in results["results"]["bindings"]:
		genres.append([result["label"]["value"].title(),result["label"]["value"].replace(" ","_")])

	return genres

def get_sub_genres(genre):
	global dbpedia
	global prefixes
	labels = []

	dbpedia.setQuery("""
		%s

		SELECT ?label WHERE {
		<http://dbpedia.org/resource/%s> dbo:musicSubgenre ?sub_genre.
		?sub_genre rdfs:label ?label.
		filter langMatches(lang(?label),"en") }

	""" % (prefixes,genre.replace(" ","_"))	)

	dbpedia.setReturnFormat(JSON)
	results = dbpedia.query().convert()

	for result in results["results"]["bindings"]:
		labels.append(result["label"]["value"])

	return labels

def get_band_members(resource):
	global dbpedia
	global prefixes
	all_members = []
	current_members = []
	past_members = []
	relationships = ['bandMember','formerBandMember']

	for item in relationships:
		dbpedia.setQuery("""
			%s

			SELECT ?label WHERE {
			<%s> dbo:%s ?member.
			?member rdfs:label ?label.
			filter langMatches(lang(?label),"en") }

		""" % (prefixes,resource,item)	)

		dbpedia.setReturnFormat(JSON)
		results = dbpedia.query().convert()

		for result in results["results"]["bindings"]:
			all_members.append((result["label"]["value"],item))

		for item in all_members:
			if item[1] == 'bandMember':
				current_members.append(item[0])
			elif item[1] == 'formerBandMember':
				past_members.append(item[0])

	return list(set(current_members)),list(set(past_members))

def get_artist_image(resource):
	global dbpedia
	global prefixes
	image_link = ""

	dbpedia.setQuery("""
			%s

			SELECT ?image WHERE {
			<%s> dbo:thumbnail ?image. }

		""" % (prefixes,resource) )

	dbpedia.setReturnFormat(JSON)
	results = dbpedia.query().convert()

	for result in results["results"]["bindings"]:
		image_link = result["image"]["value"]

	return image_link

def get_links(data):
	links = {}

	if 'url-relation-list' in data:
		for link in data['url-relation-list']:
			if "facebook" in link['target']:
				links['Facebook'] = {'url':link['target'],'icon':"fab fa-facebook"}
			elif "instagram" in link['target']:
				links['Instagram'] = {'url':link['target'],'icon':"fab fa-instagram"}
			elif "twitter" in link['target']:
				links['Twitter'] = {'url':link['target'],'icon':"fab fa-twitter"}
			elif "youtube" in link['target']:
				links['YouTube'] = {'url':link['target'],'icon':"fab fa-youtube"}
			elif "genius" in link['target']:
				links['Genius'] = {'url':link['target'],'icon':"fas fa-music"}
			elif "soundcloud" in link['target']:
				links['Soundcloud'] = {'url':link['target'],'icon':"fab fa-soundcloud"}
			elif "setlist.fm" in link['target']:
				links['Setlist.fm'] = {'url':link['target'],'icon':"fas fa-music"}
			elif "songkick" in link['target']:
				links['Songkick'] = {'url':link['target'],'icon':"fas fa-music"}
			elif "spotify" in link['target']:
				links['Spotify'] = {'url':link['target'],'icon':"fab fa-spotify"}
			elif link['type'] == 'official homepage':
				links['Homepage'] = {'url':link['target'],'icon':"fas fa-home"}

	return links

def get_location(data):
	if 'begin-area' and 'country' in data:
		try:
			return data['begin-area']['name'] + ", " + data['country']
		except KeyError:
			pass

def get_albums(data,artist):	
	studio_albums = []
	#live_albums = []
	#singles = []
	#EPs = []
	for item in data['release-group-list']:
		if item['type'] == 'Album':
			album_details = {}
			album_details['id'] = item['id']
			album_details['title'] = item['title']
#			album_details['description'] = get_description(item['title'])

			#if album_details['description'] == "":
				#album_details['description'] = get_description(item['title'] + "_(%s_album)" % (artist))
				#album_details['producer'] = get_producers(item['title'] + "_(%s_album)" % (artist))
			#elif album_details['description'] == "":
				#album_details['description'] = get_description(item['title'] + "_(album)")
				#album_details['producer'] = get_producers(item['title'] + "_(album)")
			#elif album_details['description'] == "":
				#album_details['description'] = get_description(item['title'])
				#album_details['producer'] = get_producers(item['title'])

			album_details['date'] = item['first-release-date']

			studio_albums.append(album_details)

	return sorted(studio_albums, key=lambda x: (x['date']), reverse=True)

def create_RDF(info,artist):
	rdfs = Namespace("http://www.w3.org/2000/01/rdf-schema#")
	mo = Namespace("http://purl.org/ontology/mo#")
	owl = Namespace("http://www.w3.org/2002/07/owl#")
	foaf = Namespace("http://xmlns.com/foaf/0.1/#")
	dc = Namespace("http://purl.org/dc/elements/1.1/#")
	dbo = Namespace("http://dbpedia.org/ontology/")
	dbp = Namespace("http://dbpedia.org/property/")


	if artist is True:
		artist_uri = URIRef("https://musicbrainz.org/artist/%s") % info.get('MBID')

		g = Graph()

		# Triples concerning the artist
		standard_triples = [ (artist_uri, rdfs.type, mo.MusicArtist) ]

		literal_triples = [ (artist_uri, rdfs.label, Literal(info.get('name'))),
							(artist_uri, foaf.name, Literal(info.get('name'))) ]

		uri_triples = [(artist_uri, owl.sameAs, URIRef("https://www.bbc.co.uk/music/artists/" + info.get('MBID')))]

		if 'dbpedia_ID' in info:
			try:
				uri_triples.append((artist_uri, owl.sameAs, URIRef(info.get('dbpedia_ID'))))
			except TypeError:
				pass

		if 'Homepage' in info['links']:
			uri_triples.append((artist_uri, foaf.homepage, URIRef(info['links']['Homepage']['url'])))

		for item in standard_triples:
			g.add( (item[0], item[1], item[2]) )
		
		for item in literal_triples:
			g.add( (item[0], item[1], Literal(item[2])) )

		for item in uri_triples:
			try:
				g.add( (item[0], item[1], URIRef(item[2])) )
			except TypeError:
				pass
		try:	
			for person in info['current_members']:
				g.add( (artist_uri, dbp.bandMember, Literal(person)) )
			for person in info['past_members']:
				g.add( (artist_uri, dbp.formerBandMember, Literal(person)) )
		except TypeError:
			pass

		# Triples concerning albums made by the artist
		for album in info['albums']:
			album_uri = URIRef("https://musicbrainz.org/release-group/" + album.get('id'))

			standard_triples = [ (album_uri, rdfs.type, mo.Record),
								 (album_uri, foaf.maker, artist_uri) ]

			literal_triples = [ (album_uri, rdfs.label, Literal(album.get('title'))),
 								(album_uri, dc.date, Literal(album.get('date'))) ]
			
			for item in standard_triples:
				g.add( (item[0], item[1], item[2]) )
		
			for item in literal_triples:
				g.add( (item[0], item[1], Literal(item[2])) )


		g.bind("rdfs", rdfs)
		g.bind("mo", mo)
		g.bind("owl", owl)
		g.bind("foaf", foaf)
		g.bind("dc", dc)
		g.bind("dbo", dbo)
		g.bind("dbp", dbp)

		return g.serialize("artist_rdf", format='turtle')

	else:
		album_uri = URIRef("https://musicbrainz.org/release-group/%s") % info.get('MBID')

		g = Graph()

		standard_triples = [ (album_uri, rdfs.type, mo.Record) ]

		literal_triples = [ (album_uri, rdfs.label, info.get('name')),
							(album_uri, dc.title, info.get('name')),
							(album_uri, dbo.abstract, info.get('description')) ]

		uri_triples = [ (album_uri, owl.sameAs, info.get('dbpedia_ID')) ]

		for item in standard_triples:
			g.add( (item[0], item[1], item[2]) )

		for item in literal_triples:
			g.add( (item[0], item[1], Literal(item[2])) )

		for item in uri_triples:
			try:
				g.add( (item[0], item[1], URIRef(item[2])) )
			except TypeError:
				pass

		g.bind("rdfs", rdfs)
		g.bind("mo", mo)
		g.bind("owl", owl)
		g.bind("foaf", foaf)
		g.bind("dc", dc)
		g.bind("dbo", dbo)
		g.bind("dbp", dbp)
	
		return g.serialize("album_rdf", format='turtle')

def artist_page(request,MBID):
	data = musicbrainzngs.get_artist_by_id(id=MBID, includes=['release-groups','tags','url-rels'])


	artist_info = {}
	artist_info['name'] = data['artist']['name']
	artist_info['MBID'] = MBID
	artist_info['dbpedia_ID'] = None;

	IDs = [ "http://dbpedia.org/resource/" + artist_info['name'].replace(" ","_"), 
			"http://dbpedia.org/resource/" + artist_info['name'].replace(" ","_") + "_(band)", ]

	for url in IDs:
		if get_description(url[28:]) is not "":
			artist_info['dbpedia_ID'] = url
			artist_info['description'] = get_description(url[28:])

	if artist_info['dbpedia_ID'] == None:
		artist_info['current_members'] = None
		artist_info['past_members'] = None		
	else:
		artist_info['current_members'] = get_band_members(artist_info['dbpedia_ID'])[0]
		artist_info['past_members'] = get_band_members(artist_info['dbpedia_ID'])[1]

	artist_info['genres'] = get_tags(data['artist'])
	artist_info['links'] = get_links(data['artist'])
	artist_info['hometown'] = get_location(data['artist'])
	artist_info['albums'] = get_albums(data['artist'],artist_info['name'])
	artist_info['image'] = get_artist_image(artist_info['dbpedia_ID'])
	
	rdf = create_RDF(artist_info,True)
	artist_info['artist_rdf'] = rdf
	#create_RDF(artist_info,True)

	return render(request, 'home/artist.html', {'info': artist_info})

def album_page(request,MBID):
	album_info = {}
	data = musicbrainzngs.get_release_group_by_id(id=MBID, includes=['releases','media','artists','tags'])['release-group']
	album_info['date'] = data['first-release-date']
	artist = (data['artist-credit'][0]['artist']['id'],data['artist-credit'][0]['artist']['name'])
	data = data['release-list']
	album_info['dbpedia_ID'] = None
	album_info['artist_name'] = artist[1]


	def get_tracklist(data):
		tracklist = []

		for release in data:
			if release.get('date') == album_info['date']:
				initial_release = musicbrainzngs.get_release_by_id(id=release['id'], includes=['recordings'])['release']['medium-list']
				break
			#elif release['medium-list'][0]['format'] == 'Digital Media':
				#initial_release = musicbrainzngs.get_release_by_id(id=release['id'], includes=['recordings'])['release']['medium-list']

		for track in initial_release[0]['track-list']:
			tracklist.append(track['recording']['title'])

		return tracklist

	def get_producers(album):
		global dbpedia
		global prefixes
		labels = []

		dbpedia.setQuery("""
			%s

			SELECT ?label WHERE {
			<%s> dbo:producer ?producer.
			?producer rdfs:label ?label.
			filter langMatches(lang(?label),"en") }

		""" % (prefixes,album) )

		dbpedia.setReturnFormat(JSON)
		results = dbpedia.query().convert()

		for result in results["results"]["bindings"]:
			labels.append(result["label"]["value"])

		return labels

	def get_award(album):
		global dbpedia
		labels = []

		dbpedia.setQuery("""
			PREFIX dbp: <http://dbpedia.org/property/>

			SELECT ?award WHERE {
			<%s> dbp:award ?award.}

		""" % (album) )

		dbpedia.setReturnFormat(JSON)
		results = dbpedia.query().convert()

		for result in results["results"]["bindings"]:
			labels.append(result["award"]["value"])

		return labels

	def get_bbc_review(MBID):
		global bbcmusic
		global prefixes
		reviews = []

		try:
			bbcmusic.setQuery("""
				%s

				SELECT DISTINCT ?r_name, ?rev WHERE {
		    	<http://www.bbc.co.uk/music/artists/%s#artist> foaf:made ?r1 .
		    	?r1 a mo:Record .
		    	?r1 dc:title ?r_name .
		    	?r1 rev:hasReview ?rev }

			""" % (prefixes,MBID)	)

			bbcmusic.setReturnFormat(JSON)
			results = bbcmusic.query().convert()

			for result in results["results"]["bindings"]:
				reviews.append((result["r_name"]["value"],result["rev"]["value"]))
		except EndPointInternalError:
			pass

		return reviews

	album_info['name'] = data[0]['title']
	album_info['MBID'] = MBID
	IDs = [ "http://dbpedia.org/resource/" + album_info['name'].replace(" ","_"), 
			"http://dbpedia.org/resource/" + album_info['name'].replace(" ","_") + "_(album)", 
			"http://dbpedia.org/resource/" + album_info['name'].replace(" ","_") + "_(" + artist[1].replace(" ","_") + "_album)",
			"http://dbpedia.org/resource/" + album_info['name'].replace(" ","_") + "_(" + artist[1].replace("The ","").replace(" ","_") + "_album)" ]

	for url in IDs:
		if get_description(url[28:]) is not "" and "album" in get_description(url[28:]):
			album_info['dbpedia_ID'] = url
			album_info['description'] = get_description(url[28:])

	try:
		album_info['image'] = musicbrainzngs.get_release_group_image_list(MBID)['images'][0]['thumbnails']['small']
	except (HTTPError, musicbrainzngs.musicbrainz.ResponseError):
		pass

	album_info['tracklist'] = get_tracklist(data)

	if album_info['dbpedia_ID'] is not None:
		album_info['producers'] = get_producers(album_info['dbpedia_ID'])
		album_info['genres'] = get_dbpedia_genres(album_info['dbpedia_ID'])
		album_info['award'] = get_award(album_info['dbpedia_ID'])

	for item in get_bbc_review(artist[0]):
		if item[0] == data[0]['title']:
			album_info['review'] = item[1]

	if 'award' in album_info:	
		for item in album_info['award']:
			if item not in BPI_certifications:
				album_info['award'].remove(item)

	create_RDF(album_info,False)

	return render(request, 'home/album.html', {"info": album_info})

def genre_page(request,genre):
	genre = genre.capitalize()
	info = {}
	info['name'] = genre.replace("_"," ")
	info['description'] = get_description(genre)
	info['sub_genres'] = get_sub_genres(genre)

	if info['description'] == "":
		info['description'] = get_description(genre + "_music")

	return render(request, 'home/genre.html', {"info": info})

	# Create your views here.