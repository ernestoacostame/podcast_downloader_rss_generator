import os
import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, unquote
from tqdm import tqdm
import time
from datetime import datetime
import re

class PodcastDownloader:
    def __init__(self, output_folder):
        self.output_folder = output_folder
        self.media_folder = os.path.join(output_folder, 'media')
        self.images_folder = os.path.join(output_folder, 'images')

        # Create directories if they don't exist
        for folder in [self.output_folder, self.media_folder, self.images_folder]:
            if not os.path.exists(folder):
                os.makedirs(folder)

    def sanitize_filename(self, filename):
        """Sanitize filename to be safe for all operating systems"""
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        return filename.strip().replace(' ', '_')

    def download_file(self, url, destination_folder, desc):
        """Download a file with progress bar"""
        try:
            if not url:
                return None

            filename = self.sanitize_filename(os.path.basename(unquote(urlparse(url).path)))
            destination = os.path.join(destination_folder, filename)

            if os.path.exists(destination):
                print(f"File already exists: {filename}")
                return destination

            response = requests.get(url, stream=True)
            total_size = int(response.headers.get('content-length', 0))

            with open(destination, 'wb') as file, tqdm(
                desc=desc,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as pbar:
                for data in response.iter_content(8192):
                    size = file.write(data)
                    pbar.update(size)

            return destination
        except Exception as e:
            print(f"Error downloading {url}: {str(e)}")
            return None

    def process_feed(self, rss_url):
        print(f"Downloading RSS feed from: {rss_url}")
        response = requests.get(rss_url)

        # Register all required namespaces
        ET.register_namespace('itunes', 'http://www.itunes.com/dtds/podcast-1.0.dtd')
        ET.register_namespace('podcast', 'https://podcastindex.org/namespace/1.0')
        ET.register_namespace('atom', 'http://www.w3.org/2005/Atom')
        ET.register_namespace('content', 'http://purl.org/rss/1.0/modules/content/')

        tree = ET.ElementTree(ET.fromstring(response.content))
        root = tree.getroot()
        channel = root.find('channel')

        # Download podcast cover image
        itunes_image = channel.find('.//{http://www.itunes.com/dtds/podcast-1.0.dtd}image')
        if itunes_image is not None:
            image_url = itunes_image.get('href')
            image_path = self.download_file(image_url, self.images_folder, "Downloading podcast cover")
            if image_path:
                relative_path = os.path.relpath(image_path, self.output_folder)
                itunes_image.set('href', relative_path)

                # Update regular image tag
                image = channel.find('image/url')
                if image is not None:
                    image.text = relative_path

        # Process each episode
        items = channel.findall('item')
        print(f"\nProcessing {len(items)} episodes...")

        for item in tqdm(items, desc="Processing episodes"):
            # Download episode audio
            enclosure = item.find('enclosure')
            if enclosure is not None:
                audio_url = enclosure.get('url')
                audio_path = self.download_file(audio_url, self.media_folder,
                                             f"Downloading {os.path.basename(audio_url)}")
                if audio_path:
                    relative_path = os.path.relpath(audio_path, self.output_folder)
                    enclosure.set('url', relative_path)
                    enclosure.set('length', str(os.path.getsize(audio_path)))

            # Download episode image if exists
            episode_image = item.find('.//{http://www.itunes.com/dtds/podcast-1.0.dtd}image')
            if episode_image is not None:
                image_url = episode_image.get('href')
                image_path = self.download_file(image_url, self.images_folder,
                                             f"Downloading episode image")
                if image_path:
                    relative_path = os.path.relpath(image_path, self.output_folder)
                    episode_image.set('href', relative_path)

        # Update RSS feed metadata
        self.update_feed_metadata(channel)

        # Save the new RSS feed
        output_rss = os.path.join(self.output_folder, 'feed.xml')
        tree.write(output_rss, encoding='UTF-8', xml_declaration=True)
        print(f"\nProcess completed. New RSS generated at: {output_rss}")

    def update_feed_metadata(self, channel):
        """Update feed metadata with current information"""
        # Update lastBuildDate
        last_build = channel.find('lastBuildDate')
        if last_build is not None:
            last_build.text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')

        # Update self-referential links
        for atom_link in channel.findall('{http://www.w3.org/2005/Atom}link'):
            if atom_link.get('rel') == 'self':
                atom_link.set('href', 'feed.xml')

def main():
    print("=== Podcast RSS Downloader ===")
    rss_url = input("Please enter the RSS feed URL: ").strip()
    output_folder = input("Enter the destination folder path: ").strip()

    start_time = time.time()
    try:
        downloader = PodcastDownloader(output_folder)
        downloader.process_feed(rss_url)

        elapsed_time = time.time() - start_time
        print(f"Total execution time: {elapsed_time:.2f} seconds")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()