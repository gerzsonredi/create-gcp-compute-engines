import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.backends.backend_pdf import PdfPages
import requests
from PIL import Image
import numpy as np
import io
from datetime import datetime
import os
import json
from urllib.parse import urlparse
import boto3
from dotenv import load_dotenv
load_dotenv()

class BatchResultPDFGenerator:
    def __init__(self, api_base_url="http://localhost:5000"):
        self.api_base_url = api_base_url
        self.font_title = {'weight': 'bold'}
        self.font_subtitle = {'weight': 'bold'}
        self.font_text = {}
        self.font_small = {}

    def call_full_analysis_api(self, image_urls):
        """
        Call the full-analysis API endpoint with image URLs.
        
        Args:
            image_urls (list): List of image URLs, first one is primary, rest are additional
        
        Returns:
            dict: API response or None if failed
        """
        if not image_urls:
            return None
        
        # Prepare the API payload
        payload = {
            'image_url': image_urls[0],  # Primary image
            'additional_image_urls': image_urls[1:] if len(image_urls) > 1 else []  # Additional images
        }
        
        try:
            print(f"Calling API with payload: {json.dumps(payload, indent=2)}")
            response = requests.post(
                f"{self.api_base_url}/full-analysis",
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=600  # 10 minutes timeout for full analysis
            )
            
            response.raise_for_status()
            result = response.json()
            
            print(f"API call successful for {len(image_urls)} images")
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"API call failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.json()
                    print(f"Error details: {json.dumps(error_details, indent=2)}")
                except:
                    print(f"Error response: {e.response.text}")
            return None

    def process_multiple_garments(self, garment_image_groups):
        """
        Process multiple garments through the API.
        
        Args:
            garment_image_groups (list): List of lists, each containing image URLs for one garment
                                       e.g., [['img1.jpg'], ['img2.jpg', 'img2_back.jpg'], ['img3.jpg']]
        
        Returns:
            list: List of analysis results
        """
        results = []
        
        for i, image_urls in enumerate(garment_image_groups):
            print(f"\nProcessing garment {i+1}/{len(garment_image_groups)}")
            print(f"Images: {image_urls}")
            
            result = self.call_full_analysis_api(image_urls)
            if result:
                result['garment_index'] = i + 1
                result['input_images'] = image_urls
                results.append(result)
            else:
                print(f"Failed to process garment {i+1}")
                # Add a failed result entry
                results.append({
                    'garment_index': i + 1,
                    'input_images': image_urls,
                    'success': False,
                    'error': 'API call failed',
                    'processing_timestamp': datetime.utcnow().isoformat()
                })
        
        return results

    def download_image_from_url(self, url):
        """Download image from URL and return as numpy array."""
        if not url:
            return self.create_placeholder_image("No Image")
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            img = Image.open(io.BytesIO(response.content))
            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
            return np.array(img)
        except Exception as e:
            print(f"Error downloading image from {url}: {str(e)}")
            return self.create_placeholder_image("Download Failed")
        
    def get_image_from_link(self, public_url):
        """
        Helper function that loads image from public_url or private S3 URL
        Returns numpy array
        """
        print("get_image_from_link function called")
        print(f"{public_url=}")
        try:
            # Check if it's an S3 URL that might require credentials
            if 's3' in public_url and 'amazonaws.com' in public_url:
                return self._get_image_from_s3_url(public_url)
            else:
                r = requests.get(public_url, timeout=10)
                r.raise_for_status()
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                return np.array(img)
        except Exception as e:
            print("ERROR while loading image ")
            print(e)
            return None
        
    def _get_image_from_s3_url(self, s3_url):
        """
        Helper function to get image from S3 URL using AWS credentials
        """
        try:
            # Parse the S3 URL to extract bucket and key
            # Format: https://bucket-name.s3.region.amazonaws.com/key
            # or: https://s3.region.amazonaws.com/bucket-name/key
            
            parsed_url = urlparse(s3_url)
            
            if parsed_url.hostname.startswith('s3.') or parsed_url.hostname.endswith('.amazonaws.com'):
                # Extract bucket and key from URL
                if parsed_url.hostname.endswith('.s3.amazonaws.com') or '.s3.' in parsed_url.hostname:
                    # Format: bucket-name.s3.region.amazonaws.com
                    bucket_name = parsed_url.hostname.split('.s3.')[0]
                    key = parsed_url.path.lstrip('/')
                else:
                    # Format: s3.region.amazonaws.com/bucket-name/key
                    path_parts = parsed_url.path.lstrip('/').split('/', 1)
                    bucket_name = path_parts[0]
                    key = path_parts[1] if len(path_parts) > 1 else ''
            else:
                raise ValueError(f"Unrecognized S3 URL format: {s3_url}")
            
            AWS_ACCESS_KEY_ID = os.getenv("ACCES_KEY_ARTIFACTS", "")
            AWS_SECRET_ACCESS_KEY = os.getenv("SECRET_KEY_ARTIFACTS", "")
            REGION = os.getenv("REGION", "")
            
            session = boto3.Session(
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=REGION
            )
            
            s3_client = session.client('s3')
            
            # Get the object from S3
            response = s3_client.get_object(Bucket=bucket_name, Key=key)
            image_data = response['Body'].read()
            
            # Convert to PIL Image and then numpy array
            img = Image.open(io.BytesIO(image_data)).convert("RGB")
            return np.array(img)
            
        except Exception as e:
            print(f"ERROR while loading image from S3: {e}")
            self.__logger.log(f"ERROR while loading image from S3: {e}")
            return None

    def create_placeholder_image(self, text="No Image"):
        """Create a placeholder image with text."""
        placeholder = np.ones((400, 400, 3), dtype=np.uint8) * 200
        # You could add text using PIL here if needed
        return placeholder

    def format_measurements(self, measurements_data):
        """Format measurements data for display."""
        if not measurements_data or not measurements_data.get('success'):
            return "No measurements available"
        
        measurements = measurements_data.get('measurements', {})
        text_lines = []
        
        # Add length and width if available
        if 'length' in measurements:
            text_lines.append(f"Length: {measurements['length']:.1f} px")
        if 'width' in measurements:
            text_lines.append(f"Width: {measurements['width']:.1f} px")
        
        # Add landmark points
        for key, value in measurements.items():
            if key not in ['length', 'width'] and isinstance(value, list) and len(value) == 2:
                text_lines.append(f"{key.upper()}: ({value[0]}, {value[1]})")
        
        return '\n'.join(text_lines) if text_lines else "No measurements"

    def format_category_prediction(self, category_data, additional_category):
        """Format category prediction data for display."""
        if not category_data or not category_data.get('success'):
            return "No category prediction"
        
        topx = category_data.get('topx', [])
        if not topx:
            return "No predictions available"
        
        text_lines = []
        text_lines.append(additional_category)
        for i, prediction in enumerate(topx[:3]):  # Show top 3
            if isinstance(prediction, list) and len(prediction) >= 2:
                category, confidence = prediction[0], prediction[1]
                text_lines.append(f"{i+1}. {category}: {confidence:.1%}")
        return '\n'.join(text_lines)

    def format_condition_prediction(self, condition_data):
        """Format condition prediction data for display."""
        if not condition_data:
            return "No condition assessment"
        
        rating = condition_data.get('condition_rating', 'N/A')
        description = condition_data.get('condition_description', '')
        
        text_lines = [f"{rating}"]
        if description:
            text_lines.append(f"{description}")
        
        return '\n'.join(text_lines)

    def create_batch_pdf_report(self, results_list, output_filename="batch_garment_analysis.pdf"):
        """Create a comprehensive PDF report from multiple analysis results."""
        print(f"Creating batch PDF report with {len(results_list)} garments...")
        # Sort results by category prediction
        
            
        # Sort the results list by top category
        # print("Sorting result_list based on categories")
        # sorted_results = sorted(results_list, key=get_top_category)
        
        # print(f"Results sorted by category:")
        # for i, result in enumerate(sorted_results):
        #     category = get_top_category(result)
        #     if category != 'zzz_no_category':
        #         print(f"  {i+1}. {category.title()}")
        #     else:
        #         print(f"  {i+1}. No category prediction")    
        sorted_results = results_list
        try:
            with PdfPages(output_filename) as pdf:
                # Title page
                self.create_title_page(pdf, len(sorted_results))
                
                # Summary page
                self.create_summary_page(pdf, sorted_results)
                
                # Individual garment pages
                for idx, result in enumerate(sorted_results, start=1):
                    self.create_garment_page(pdf, result, garment_num=idx)
            
            print(f"Batch PDF report created successfully: {output_filename}")
            return output_filename
            
        except Exception as e:
            print(f"Error creating batch PDF report: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def create_title_page(self, pdf, num_garments):
        """Create the title page."""
        fig = plt.figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # Title
        ax.text(0.5, 0.7, 'Batch Garment Analysis Report', 
                ha='center', va='center', fontdict=self.font_title, fontsize=24)
        
        # Details
        ax.text(0.5, 0.5, f'Number of Garments Analyzed: {num_garments}', 
                ha='center', va='center', fontdict=self.font_subtitle, fontsize=16)
        
        ax.text(0.5, 0.4, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                ha='center', va='center', fontdict=self.font_text, fontsize=14)
        
        # Add a border
        rect = patches.Rectangle((0.1, 0.1), 0.8, 0.8, linewidth=2, 
                               edgecolor='black', facecolor='none', transform=ax.transAxes)
        ax.add_patch(rect)
        
        pdf.savefig(fig, bbox_inches='tight', dpi=150)
        plt.close(fig)

    def create_summary_page(self, pdf, results_list):
        """Create a summary page with overview of all garments."""
        fig = plt.figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # Title
        ax.text(0.5, 0.95, 'Analysis Summary', 
                ha='center', va='top', fontdict=self.font_title, fontsize=20)
        
        # Create summary text
        summary_lines = []
        successful_analyses = sum(1 for r in results_list if r.get('success', False))
        failed_analyses = len(results_list) - successful_analyses
        
        summary_lines.append(f"Total Garments: {len(results_list)}")
        summary_lines.append(f"Successful Analyses: {successful_analyses}")
        summary_lines.append(f"Failed Analyses: {failed_analyses}")
        summary_lines.append("")
        
        # Individual garment summaries
        for i, result in enumerate(results_list):
            garment_num = i + 1
            if result.get('success', False):
                # Get top category prediction
                category_pred = result.get('category_prediction', {})
                if category_pred.get('success') and category_pred.get('topx'):
                    top_category = category_pred['topx'][0][0]
                    confidence = category_pred['topx'][0][1]
                    summary_lines.append(f"Garment {garment_num}: {top_category} ({confidence:.1%})")
                else:
                    summary_lines.append(f"Garment {garment_num}: Analysis completed")
            else:
                summary_lines.append(f"Garment {garment_num}: Analysis failed")
        
        summary_text = '\n'.join(summary_lines)
        
        ax.text(0.05, 0.85, summary_text, 
                transform=ax.transAxes, 
                fontdict=self.font_text,
                verticalalignment='top',
                bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.3))
        
        pdf.savefig(fig, bbox_inches='tight', dpi=150)
        plt.close(fig)

    def create_garment_page(self, pdf, result, garment_num = -1):
        """Create a page for individual garment analysis."""
        if not result.get('success', False):
            self.create_error_page(pdf, result)
            return
        
        fig = plt.figure(figsize=(11, 14))  # Taller page for more content
        
        # Create a complex grid layout
        gs = fig.add_gridspec(4, 3, height_ratios=[0.5, 3, 1.5, 1], hspace=0.4, wspace=0.3)
        
        # Title
        title_ax = fig.add_subplot(gs[0, :])
        # garment_num = result.get('garment_index', '?')
        title_ax.text(0.5, 0.5, f'Garment #{garment_num} Analysis', 
                     ha='center', va='center', fontdict=self.font_subtitle, fontsize=18)
        title_ax.axis('off')
        
        # Images
        try:
            original_img = self.get_image_from_link(result.get('original_image', ''))
            segmented_img = self.get_image_from_link(result.get('segmented_image', ''))
            
            measurements_data = result.get('measurements', {})
            measured_img_url = measurements_data.get('url', '')
            measured_img = self.get_image_from_link(measured_img_url) if measured_img_url else original_img
            
            # Display images
            ax1 = fig.add_subplot(gs[1, 0])
            ax1.imshow(original_img)
            ax1.axis('off')
            ax1.set_title('Original', fontdict=self.font_small)
            
            # ax2 = fig.add_subplot(gs[1, 1])
            # ax2.imshow(segmented_img)
            # ax2.axis('off')
            # ax2.set_title('Segmented', fontdict=self.font_small)
            
            ax3 = fig.add_subplot(gs[1, 2])
            ax3.imshow(measured_img)
            ax3.axis('off')
            ax3.set_title('Measured', fontdict=self.font_small)

            
        except Exception as e:
            print(f"Error loading images for garment {garment_num}: {str(e)}")
        
        # Analysis results
        results_ax = fig.add_subplot(gs[2, :])
        results_ax.axis('off')
        
        # Format analysis data

        category_text = self.format_category_prediction(result.get('category_prediction'), get_top_category(result))
        # condition_text = self.format_condition_prediction(result.get('condition_prediction'))
        measurements_text = self.format_measurements(result.get('measurements'))
        
        # Create three columns of text
        col1_text = f"CATEGORY:\n{category_text}"
        # col2_text = f"CONDITION:\n{condition_text}"
        col3_text = f"MEASUREMENTS:\n{measurements_text}"
        
        results_ax.text(0.02, 0.95, col1_text, 
                       transform=results_ax.transAxes, 
                       fontdict=self.font_small,
                       verticalalignment='top',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen", alpha=0.3))
        
        # results_ax.text(0.35, 0.95, col2_text, 
        #                transform=results_ax.transAxes, 
        #                fontdict=self.font_small,
        #                verticalalignment='top',
        #                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightcoral", alpha=0.3))
        
        results_ax.text(0.68, 0.95, col3_text, 
                       transform=results_ax.transAxes, 
                       fontdict=self.font_small,
                       verticalalignment='top',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.3))
        
        # Processing info
        info_ax = fig.add_subplot(gs[3, :])
        info_ax.axis('off')
        
        input_images = result.get('input_images', [])
        processing_time = result.get('processing_timestamp', 'N/A')
        
        info_text = f"""
Processing Time: {processing_time}
Input Images: {len(input_images)}
Original URL: {result.get('original_image', 'N/A')[:80]}...
Segmented URL: {result.get('segmented_image', 'N/A')[:80]}...
        """.strip()
        
        info_ax.text(0.05, 0.8, info_text, 
                    transform=info_ax.transAxes, 
                    fontdict=self.font_small,
                    verticalalignment='top',
                    fontfamily='monospace',
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.3))
        
        pdf.savefig(fig, bbox_inches='tight', dpi=150)
        plt.close(fig)

    def create_error_page(self, pdf, result):
        """Create a page for failed analysis."""
        fig = plt.figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        garment_num = result.get('garment_index', '?')
        error_msg = result.get('error', 'Unknown error')
        input_images = result.get('input_images', [])
        
        ax.text(0.5, 0.7, f'Garment #{garment_num} - Analysis Failed', 
                ha='center', va='center', fontdict=self.font_subtitle, fontsize=18, color='red')
        
        error_text = f"""
Error: {error_msg}

Input Images:
{chr(10).join(f"  {i+1}. {url}" for i, url in enumerate(input_images))}

Processing Time: {result.get('processing_timestamp', 'N/A')}
        """.strip()
        
        ax.text(0.5, 0.4, error_text, 
                ha='center', va='center', fontdict=self.font_text,
                bbox=dict(boxstyle="round,pad=0.5", facecolor="mistyrose", alpha=0.8))
        
        pdf.savefig(fig, bbox_inches='tight', dpi=150)
        plt.close(fig)


# Main function to use the batch processor
def create_batch_report_from_image_groups(garment_image_groups, output_filename=None, api_base_url="http://localhost:5000"):
    """
    Create a batch PDF report from multiple garment image groups.
    
    Args:
        garment_image_groups (list): List of lists, each containing image URLs for one garment
        output_filename (str): Output PDF filename (optional)
        api_base_url (str): Base URL for the API
    
    Returns:
        str: Path to created PDF file or None if failed
    """
    if not output_filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"batch_garment_analysis_{timestamp}.pdf"
    
    # Ensure we're using the reports directory
    if not output_filename.startswith('/app/reports/'):
        output_filename = f"/app/reports/{os.path.basename(output_filename)}"
    
    # Create output directory if needed (inside container)
    os.makedirs("/app/reports", exist_ok=True)
    
    # Create the batch processor
    processor = BatchResultPDFGenerator(api_base_url)
    
    # Process all garments
    print(f"Processing {len(garment_image_groups)} garment groups...")
    results = processor.process_multiple_garments(garment_image_groups)
    
    # Create the PDF report
    return processor.create_batch_pdf_report(results, output_filename)

def get_top_category(result):
    """Extract the top category name from a result for sorting."""
    try:
        # category_pred = result.get('category_prediction', {})
        # if category_pred.get('success') and category_pred.get('topx'):
        #     # Get the category with highest probability (first in topx list)
        #     top_category = category_pred['topx'][0][0]
        #     print(f"{top_category=}")
        #     return top_category.lower()  # Convert to lowercase for consistent sorting
        # else:
        #     return 'zzz_no_category'  # Put items without category at the end
        category_pred = result.get('measurements', {})
        if category_pred.get('success') and category_pred.get('category_name'):
            top_category = category_pred.get('category_name')
            print(f"{top_category=}")
            return top_category.lower()
        else:
            return 'zzz_no_category' 
    except (KeyError, IndexError, TypeError):
        return 'zzz_no_category'  # Put malformed entries at the end

# Example usage
if __name__ == "__main__":
    garment_image_groups = [
        [
            "https://media.remix.eu/files/20-2025/Majki-kas-pantalon-Samsoe---Samsoe-132036343b.jpg",
            "https://media.remix.eu/files/20-2025/Majki-kas-pantalon-Samsoe---Samsoe-132036343c.jpg", 
            "https://media.remix.eu/files/20-2025/Majki-kas-pantalon-Samsoe---Samsoe-132036343a.jpg"
        ]
    ]
    
    # Create the batch report
    pdf_path = create_batch_report_from_image_groups(
        garment_image_groups, 
        output_filename="reports/batch_analysis_report.pdf"
    )
    
    if pdf_path:
        print(f"Batch report created successfully: {pdf_path}")
    else:
        print("Failed to create batch report")