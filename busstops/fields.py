import autoslug


# this is almost the same as the autosplug package's generate_unique_slug,
# but it uses `.exists()` to check for the existence of `rivals``,
# which is a tiny bit more efficient
def generate_unique_slug(field, instance, slug, manager):
    """
    Generates unique slug by adding a number to given value until no model
    instance can be found with such slug. If ``unique_with`` (a tuple of field
    names) was specified for the field, all these fields are included together
    in the query when looking for a "rival" model instance.
    """

    original_slug = slug = autoslug.utils.crop_slug(field, slug)

    default_lookups = tuple(
        autoslug.utils.get_uniqueness_lookups(field, instance, field.unique_with)
    )

    index = 1

    if not manager:
        manager = field.model._default_manager

    # keep changing the slug until it is unique
    while True:
        # find instances with same slug
        lookups = dict(default_lookups, **{field.name: slug})
        rivals = manager.filter(**lookups)
        if instance.pk:
            rivals = rivals.exclude(pk=instance.pk)

        if not rivals.exists():
            # the slug is unique, no model uses it
            return slug

        # the slug is not unique; change once more
        index += 1

        # ensure the resulting string is not too long
        tail_length = len(field.index_sep) + len(str(index))
        combined_length = len(original_slug) + tail_length
        if field.max_length < combined_length:
            original_slug = original_slug[: field.max_length - tail_length]

        # re-generate the slug
        data = dict(slug=original_slug, sep=field.index_sep, index=index)
        slug = "%(slug)s%(sep)s%(index)d" % data

        # ...next iteration...


autoslug.utils.generate_unique_slug = generate_unique_slug


class AutoSlugField(autoslug.AutoSlugField):
    def pre_save(self, instance, add):
        if add:
            return super().pre_save(instance, add)

        return self.value_from_object(instance)
