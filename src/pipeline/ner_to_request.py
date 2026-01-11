"""Normalize extracted entities into a SofaRequest payload."""

# TODO: define a mapping between NER outputs and SofaRequest fields.
# TODO: validate and normalize entity values (materials, dimensions, styles).

def normalize_entities(entities):
    """Normalize raw NER entities into canonical request fields."""
    # TODO: implement normalization logic once schema is finalized.
    return {
        "raw_entities": entities,
    }


def map_ner_to_request(entities):
    """Map normalized entities into a SofaRequest structure."""
    # TODO: build SofaRequest payload structure from normalized entities.
    return {
        "request": normalize_entities(entities),
    }
