import datetime
import os
from functools import wraps

import flask
import sys

import logging

import yaml
from flask import jsonify, Blueprint

import __version__
import controller
from constants import TRANSLATION
from constants.common import LANGUAGES, LANGUAGE_ENGLISH, ORDO_DIR
from api.exceptions import InvalidInput, ProperNotFound, SupplementNotFound, SectionNotFound
from kalendar.models import Day, Calendar
from utils import get_pregenerated_proper, format_propers, get_supplement, supplement_index

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='[%(asctime)s ] %(levelname)s in %(module)s: %(message)s')


api = Blueprint('apiv5', __name__)


def validate_locale(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if kwargs['lang'] not in LANGUAGES.keys():
            return jsonify({'error': "Not found"}), 404
        return f(*args, **kwargs)
    return decorated_function


@api.route('/<string:lang>/api/v5/proper/<string:date_or_id>')
@validate_locale
def v5_proper(date_or_id: str, lang: str = LANGUAGE_ENGLISH):
    try:
        date_object = datetime.datetime.strptime(date_or_id, "%Y-%m-%d").date()
    except ValueError:
        # Not a valid date, getting by ID
        proper_id = {i['ref']: i['id'] for i in TRANSLATION[lang].VOTIVE_MASSES}.get(date_or_id, date_or_id)
        try:
            pregenerated_proper = get_pregenerated_proper(lang, proper_id)
            if pregenerated_proper is not None:
                return jsonify(pregenerated_proper)
            proper_vernacular, proper_latin = controller.get_proper_by_id(proper_id, lang)
            return jsonify(format_propers([[proper_vernacular, proper_latin]]))
        except InvalidInput as e:
            return jsonify({'error': str(e)}), 400
        except ProperNotFound as e:
            return jsonify({'error': str(e)}), 404
        except SectionNotFound as e:
            return jsonify({'error': str(e)}), 500
    else:
        # Valid date, getting day's proper
        day: Day = controller.get_day(date_object, lang)
        pregenerated_proper = get_pregenerated_proper(lang, day.get_celebration_id(), day.get_tempora_id())
        if pregenerated_proper:
            return jsonify(pregenerated_proper)
        return jsonify(format_propers(day.get_proper(), day))


@api.route('/<string:lang>/api/v5/ordo')
@validate_locale
def v5_ordo(lang: str = LANGUAGE_ENGLISH):
    with open(os.path.join(ORDO_DIR, lang, 'ordo.yaml')) as fh:
        content = yaml.full_load(fh)
        return jsonify(content)


def supplement_response(lang, id_, subdir):
    try:
        supplement_yaml = get_supplement(lang, id_, subdir)
    except SupplementNotFound:
        return jsonify({'error': "Not found"}), 404
    else:
        return jsonify([supplement_yaml])


@api.route("/<string:lang>/api/v5/supplement/<string:id_>")
@api.route("/<string:lang>/api/v5/supplement/<subdir>/<string:resource>")
@validate_locale
def v5_supplement(id_: str, subdir: str = None, lang: str = LANGUAGE_ENGLISH):
    return supplement_response(lang, id_, subdir)


@api.route('/<string:lang>/api/v5/calendar')
@api.route('/<string:lang>/api/v5/calendar/<int:year>')
@validate_locale
def v5_calendar(year: int = None, lang: str = LANGUAGE_ENGLISH):
    if year is None:
        year = datetime.datetime.now().date().year
    missal: Calendar = controller.get_calendar(year, lang)
    container = []
    for date_, day in missal.items():
        title = day.get_celebration_name()
        tempora = day.get_tempora_name()
        tags = []
        if tempora and title != tempora:
            tags.append(tempora)
        container.append({
            "title": title,
            "tags": tags,
            "colors": day.get_celebration_colors(),
            "rank": day.get_celebration_rank(),
            "id": date_.strftime("%Y-%m-%d"),
            "commemorations": day.get_commemorations_titles()
        })
    return jsonify(container)


@api.route('/<string:lang>/api/v5/votive')
@validate_locale
def v5_votive(lang: str = LANGUAGE_ENGLISH):
    index = TRANSLATION[lang].VOTIVE_MASSES
    return jsonify([{
        "id": i['ref'],
        "title": i["title"],
        "tags": i["tags"]
    } for i in index])


@api.route('/<string:lang>/api/v5/oratio')
@validate_locale
def v5_oratio(lang: str = LANGUAGE_ENGLISH):
    return jsonify(supplement_index.get_oratio_index(lang))


@api.route('/<string:lang>/api/v5/oratio/<string:id_>')
@validate_locale
def v5_oratio_by_id(id_, lang: str = LANGUAGE_ENGLISH):
    return supplement_response(lang, id_, 'oratio')


@api.route('/<string:lang>/api/v5/canticum')
@validate_locale
def v5_canticum(lang: str = LANGUAGE_ENGLISH):
    return jsonify(supplement_index.get_canticum_index(lang))


@api.route('/<string:lang>/api/v5/canticum/<string:id_>')
@validate_locale
def v5_canticum_by_id(id_, lang: str = LANGUAGE_ENGLISH):
    return supplement_response(lang, id_, 'canticum')


@api.route('/<string:lang>/api/v5/icalendar')
@api.route('/<string:lang>/api/v5/icalendar/<int:rank>')
@validate_locale
def v5_ical(rank: int = 2, lang: str = LANGUAGE_ENGLISH):
    try:
        rank = int(rank)
        assert rank in range(1, 5)
    except (ValueError, AssertionError):
        rank = 2

    response = flask.Response(controller.get_ical(lang, rank))
    response.headers['Content-Type'] = 'text/calendar; charset=utf-8'
    return response


@api.route('/<string:lang>/api/v5/version')
@api.route('/<string:lang>/api/v5/version')
@validate_locale
def v5_version(lang: str = LANGUAGE_ENGLISH):
    return jsonify({"version": __version__.__version__})
