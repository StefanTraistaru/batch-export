#! /usr/bin/env python

import sys
sys.path.append('/usr/share/inkscape/extensions')
import inkex
import os
import subprocess
import tempfile
import shutil
import copy
import logging

class Options():
    def __init__(self, batch_exporter):
        self.current_file = batch_exporter.options.input_file

        self.export_type = 'svg'
        if batch_exporter.options.export_type == '2':
            self.export_type = 'png'
        self.output_path = os.path.expanduser(batch_exporter.options.path)

        self.use_text_prefix = self._str_to_bool(batch_exporter.options.use_text_prefix)
        if self.use_text_prefix:
            self.text_prefix = batch_exporter.options.text_prefix

        self.use_number_prefix = self._str_to_bool(batch_exporter.options.use_number_prefix)
        if self.use_number_prefix:
            self.number_max_digits = batch_exporter.options.number_max_digits
            self.max_number = self.number_max_digits * 10 - 1

        self.use_background_layers = self._str_to_bool(batch_exporter.options.use_background_layers)
        self.skip_hidden_layers = self._str_to_bool(batch_exporter.options.skip_hidden_layers)
        self.overwrite_files = self._str_to_bool(batch_exporter.options.overwrite_files)

        self.use_logging = self._str_to_bool(batch_exporter.options.use_logging)
        if self.use_logging:
            self.log_path = os.path.expanduser(batch_exporter.options.log_path)
            logging.basicConfig(filename=os.path.join(self.log_path, 'batch_export.log'),level=logging.DEBUG)

    def _str_to_bool(self, str):
        if str.lower() == 'true':
            return True
        return False

    def __str__(self):
        print = "===> EXTENSION PARAMETERS\n"
        print += "Current file: {}\n".format(self.current_file)
        print += "Export type: {}\n".format(self.export_type)
        print += "Path: {}\n".format(self.output_path)
        print += "Use text prefix: {}\n".format(self.use_text_prefix)
        if self.use_text_prefix:
            print += "Text prefix: {}\n".format(self.text_prefix)
        print += "Use number prefix: {}\n".format(self.use_number_prefix)
        if self.use_number_prefix:
            print += "Max digits: {}\n".format(self.number_max_digits)
        print += "Use background layers: {}\n".format(self.use_background_layers)
        print += "Skip hidden layers: {}\n".format(self.skip_hidden_layers)
        print += "Overwrite files: {}\n".format(self.overwrite_files)
        print += "Use logging: {}\n".format(self.use_logging)
        if self.use_logging:
            print += "Log path: {}\n".format(self.log_path)

        return print

class BatchExporter(inkex.Effect):
    def __init__(self):
        """init the effetc library and get options from gui"""
        inkex.Effect.__init__(self)
        # Export parameters
        self.arg_parser.add_argument("--export-type", action="store", type=str, dest="export_type", default="1", help="")
        self.arg_parser.add_argument("--path", action="store", type=str, dest="path", default="~/", help="export path")
        # Prefix parameters
        self.arg_parser.add_argument("--use-text-prefix", action="store", type=str, dest="use_text_prefix", default=False, help="")
        self.arg_parser.add_argument("--prefix-text", action="store", type=str, dest="text_prefix", default="prefix", help="")
        self.arg_parser.add_argument("--use-number-prefix", action="store", type=str, dest="use_number_prefix", default=False, help="")
        self.arg_parser.add_argument("--number-max-digits", action="store", type=int, dest="number_max_digits", default=3, help="")
        # Other
        self.arg_parser.add_argument("--use-background-layers", action="store", type=str, dest="use_background_layers", default=False, help="")
        self.arg_parser.add_argument("--skip-hidden-layers", action="store", type=str, dest="skip_hidden_layers", default=False, help="")
        self.arg_parser.add_argument("--overwrite-files", action="store", type=str, dest="overwrite_files", default=False, help="")
        # Log
        self.arg_parser.add_argument("--use-logging", action="store", type=str, dest="use_logging", default=False, help="")
        self.arg_parser.add_argument("--log-path", action="store", type=str, dest="log_path", default="~/", help="")

        # HACK - the script is called with a "--tab controls" option as an argument from the notebook param in the inx file.
        # This argument is not used in the script. It's purpose is to suppress an error when the script is called.
        self.arg_parser.add_argument("--tab", action="store", type=str, dest="tab", default="controls", help="")

    def effect(self):
        counter = 1

        # Check user options
        options = Options(self)
        logging.debug(options)

        # Get the layers from the current file
        layers = self.get_layers(options.current_file, options.skip_hidden_layers)

        # For each layer export a file
        for (layer_id, layer_label, layer_type) in layers:
            if layer_type == "fixed":
                continue

            show_layer_ids = [layer[0] for layer in layers if layer[2] == "fixed" or layer[0] == layer_id]

            # Create the output folder if it doesn't exist
            if not os.path.exists(os.path.join(options.output_path)):
                os.makedirs(os.path.join(options.output_path))

            with tempfile.NamedTemporaryFile() as temporary_file:
                # Construct the name of the exported file
                if options.use_text_prefix and options.use_number_prefix:
                    file_name = "{}_{}_{}.{}".format(str(counter).zfill(options.number_max_digits), options.text_prefix, layer_label, options.export_type)
                elif options.use_text_prefix:
                    file_name = "{}_{}.{}".format(options.text_prefix, layer_label, options.export_type)
                elif options.use_number_prefix:
                    file_name = "{}_{}.{}".format(str(counter).zfill(options.number_max_digits), layer_label, options.export_type)
                else:
                    file_name = "{}.{}".format(layer_label, options.export_type)

                # Check if the file exists. If not, export it.
                destination_path = os.path.join(options.output_path, file_name)
                if not options.overwrite_files and os.path.exists(destination_path):
                    logging.debug("  File already exists: {}\n".format(file_name))
                    continue

                # Create a new file in which we delete unwanted layers to keep the exported file size to a minimum
                temporary_file_path = temporary_file.name
                logging.debug("  Preparing layer [{}, {}]".format(layer_id, layer_label))
                self.manage_layers(temporary_file_path, show_layer_ids)

                logging.debug("  Exporting [{}, {}] as {}\n".format(layer_id, layer_label, file_name))
                if options.export_type == 'svg':
                    self.exportToSVG(temporary_file_path, destination_path)
                else:
                    self.exportToPNG(temporary_file_path, destination_path)

            counter += 1
            if options.use_number_prefix and counter > options.max_number:
                logging.debug('With a max digit number set to {} the maximum number of SVGs that can be exported with an automated number prefix is {}. '\
                               'In this file there are more layers to export than the maximum number. Only the first {} layers have been exported. '\
                               'Increase the max digit number to be able to export all of them.'.format(options.number_max_digits, options.max_number, options.max_number))
                inkex.errormsg('With a max digit number set to {} the maximum number of SVGs that can be exported with an automated number prefix is {}. '\
                               'In this file there are more layers to export than the maximum number. Only the first {} layers have been exported. '\
                               'Increase the max digit number to be able to export all of them.'.format(options.number_max_digits, options.max_number, options.max_number))
                break

    def manage_layers(self, temporary_file_path, show_layer_ids):
        # Create a copy of the current document
        doc = copy.deepcopy(self.document)
        for layer in doc.xpath('//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS):
            layer_id = layer.attrib["id"]
            layer_label = layer.attrib["{%s}label" % layer.nsmap['inkscape']]

            # Display/Delete layers
            if layer_id not in show_layer_ids:
                layer.getparent().remove(layer)
                logging.debug("    Deleting: [{}, {}]".format(layer_id, layer_label))

        doc.write(temporary_file_path)

    def get_layers(self, file, skip_hidden_layers):
        svg_layers = self.document.xpath('//svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS)
        layers = []

        for layer in svg_layers:
            label_attrib_name = "{%s}label" % layer.nsmap['inkscape']
            if label_attrib_name not in layer.attrib:
                continue

            # Skipping hidden layers
            if skip_hidden_layers and 'style' in layer.attrib:
                if 'display:none' in layer.attrib['style']:
                    logging.debug("  Skip: [{}, {}]".format(layer.attrib["id"], layer.attrib[label_attrib_name]))
                    continue

            layer_id = layer.attrib["id"]
            layer_label = layer.attrib[label_attrib_name]

            # Checking for background (fixed) layers
            if layer_label.lower().startswith("[fixed] "):
                layer_type = "fixed"
                layer_label = layer_label[8:]
            else:
                layer_type = "export"

            logging.debug("  Use : [{}, {}, {}]".format(layer_id, layer_label, layer_type))
            layers.append([layer_id, layer_label, layer_type])

        logging.debug("  TOTAL NUMBER OF LAYERS: {}\n".format(len(layers)))
        return layers

    def exportToSVG(self, svg_path, output_path):
        args = [
            'inkscape',
            '--vacuum-defs',
            '--export-area-page',
            '--export-plain-svg',
            '--export-filename=%s' % output_path,
            svg_path
        ]

        try:
            with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
                proc.wait(timeout=300)
        except OSError:
            logging.debug('Error while exporting file {}.'.format(output_path))
            inkex.errormsg('Error while exporting file {}.'.format(output_path))
            exit()

    def exportToPNG(self, svg_path, output_path):
        # TODO: PNG export DPI
        args = [
            'inkscape',
            '--vacuum-defs',
            '--export-area-page',
            '--export-filename=%s' % output_path,
            svg_path
        ]

        try:
            with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
                proc.wait(timeout=300)
        except OSError:
            logging.debug('Error while exporting file {}.'.format(output_path))
            inkex.errormsg('Error while exporting file {}.'.format(output_path))
            exit()

def _main():
    exporter = BatchExporter()
    exporter.run()
    exit()

if __name__ == "__main__":
    _main()
