import autoslug


class AutoSlugField(autoslug.AutoSlugField):
    def pre_save(self, instance, add):
        if add:
            return super().pre_save(instance, add)

        return self.value_from_object(instance)
