

def image_manager(file_name):

    # from common.models import Gallery

    # gallery = Gallery.objects.filter(url = file_name).first()
    # return gallery
    from common.models import Gallery
    name = file_name.split("/media/")[-1]

    gallery = Gallery.objects.filter(url = name).first()
    return gallery
