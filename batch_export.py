#! /usr/bin/env python

import sys
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
        self.output_path = os.path.normpath(batch_exporter.options.path)
        self.use_background_layers = self._str_to_bool(batch_exporter.options.use_background_layers)
        self.skip_hidden_layers = self._str_to_bool(batch_exporter.options.skip_hidden_layers)
        self.overwrite_files = self._str_to_bool(batch_exporter.options.overwrite_files)

        self.naming_scheme = "simple"
        self.use_number_prefix = batch_exporter.options.use_number_prefix
        if batch_exporter.options.naming_scheme == '2':
            self.naming_scheme = "advanced"
            self.name_template = batch_exporter.options.name_template

        self.use_logging = self._str_to_bool(batch_exporter.options.use_logging)
        if self.use_logging:
            self.log_path = os.path.expanduser(batch_exporter.options.log_path)
            self.overwrite_log = self._str_to_bool(batch_exporter.options.overwrite_log)
            log_file_name = os.path.join(self.log_path, 'batch_export.log')
            if self.overwrite_log and os.path.exists(log_file_name):
                logging.basicConfig(filename=log_file_name, filemode="w", level=logging.DEBUG)
            else:
                logging.basicConfig(filename=log_file_name, level=logging.DEBUG)

    def _str_to_bool(self, str):
        if str.lower() == 'true':
            return True
        return False

    def __str__(self):
        print = "===> EXTENSION PARAMETERS\n"
        print += "Current file: {}\n".format(self.current_file)
        print += "Export type: {}\n".format(self.export_type)
        print += "Path: {}\n".format(self.output_path)
        print += "Use background layers: {}\n".format(self.use_background_layers)
        print += "Skip hidden layers: {}\n".format(self.skip_hidden_layers)
        print += "Overwrite files: {}\n".format(self.overwrite_files)
        print += "Naming scheme: {}\n".format(self.naming_scheme)
        if self.naming_scheme == 'simple':
            print += "Add number as prefix: {}".format(self.use_number_prefix)
        else:
            print += "Name template: {}\n".format(self.name_template)

        print += "Use logging: {}\n".format(self.use_logging)
        print += "Overwrite log: {}\n".format(self.overwrite_log)
        if self.use_logging:
            print += "Log path: {}\n".format(self.log_path)

        return print

class BatchExporter(inkex.Effect):
    def __init__(self):
        """init the effetc library and get options from gui"""
        inkex.Effect.__init__(self)
        # Export parameters
        self.arg_parser.add_argument("--export-type", action="store", type=str, dest="export_type", default="1", help="")
        self.arg_parser.add_argument("--path", action="store", type=str, dest="path", default="", help="export path")

        # Other
        self.arg_parser.add_argument("--use-background-layers", action="store", type=str, dest="use_background_layers", default=False, help="")
        self.arg_parser.add_argument("--skip-hidden-layers", action="store", type=str, dest="skip_hidden_layers", default=False, help="")
        self.arg_parser.add_argument("--overwrite-files", action="store", type=str, dest="overwrite_files", default=False, help="")

        # Naming parameters
        self.arg_parser.add_argument("--naming-scheme", action="store", type=str, dest="naming_scheme", default="1", help="")
        self.arg_parser.add_argument("--use-number-prefix", action="store", type=str, dest="use_number_prefix", default=False, help="")
        self.arg_parser.add_argument("--name-template", action="store", type=str, dest="name_template", default="[LAYER_NAME]", help="")

        # Log
        self.arg_parser.add_argument("--use-logging", action="store", type=str, dest="use_logging", default=False, help="")
        self.arg_parser.add_argument("--overwrite-log", action="store", type=str, dest="overwrite_log", default=False, help="")
        self.arg_parser.add_argument("--log-path", action="store", type=str, dest="log_path", default="", help="")

        # HACK - the script is called with a "--tab controls" option as an argument from the notebook param in the inx file.
        # This argument is not used in the script. It's purpose is to suppress an error when the script is called.
        self.arg_parser.add_argument("--tab", action="store", type=str, dest="tab", default="controls", help="")

    def effect(self):
        counter = 1

        # Check user options
        options = Options(self)
        logging.debug(options)

        # Get the layers from the current file
        layers = self.get_layers(options.current_file, options.skip_hidden_layers, options.use_background_layers)

        # For each layer export a file
        for (layer_id, layer_label, layer_type) in layers:
            if layer_type == "fixed":
                continue

            show_layer_ids = [layer[0] for layer in layers if layer[2] == "fixed" or layer[0] == layer_id]

            # Create the output folder if it doesn't exist
            if not os.path.exists(os.path.join(options.output_path)):
                os.makedirs(os.path.join(options.output_path))

            # Construct the name of the exported file
            if options.naming_scheme == 'simple':
                file_name = self.get_simple_name(options.use_number_prefix, counter, layer_label)
            else:
                file_name = self.get_advanced_name(options.name_template, counter, layer_label)
            file_name = "{}.{}".format(file_name, options.export_type)
            logging.debug("  File name: {}".format(file_name))

            # Check if the file exists. If not, export it.
            destination_path = os.path.join(options.output_path, file_name)
            if not options.overwrite_files and os.path.exists(destination_path):
                logging.debug("  File already exists: {}\n".format(file_name))
                # TODO: Should this be the expected functionality of this scenario?
                counter += 1
                continue

            # Create a new file in which we delete unwanted layers to keep the exported file size to a minimum
            logging.debug("  Preparing layer [{}, {}]".format(layer_id, layer_label))
            temporary_file_path = self.manage_layers("", show_layer_ids)

            logging.debug("  Exporting [{}, {}] as {}\n".format(layer_id, layer_label, file_name))
            if options.export_type == 'svg':
                self.exportToSVG(temporary_file_path, destination_path)
            else:
                self.exportToPNG(temporary_file_path, destination_path)

            # Clean up - delete the temporary file we have created
            os.remove(temporary_file_path)

            counter += 1

    def get_simple_name(self, use_number_prefix, counter, layer_label):
        if use_number_prefix:
            return "{}_{}".format(counter, layer_label)

        return layer_label

    def get_advanced_name(self, template_name, counter, layer_label):
        file_name = template_name
        file_name = file_name.replace('[LAYER_NAME]', layer_label)
        file_name = file_name.replace("[NUM]", str(counter))
        file_name = file_name.replace("[NUM-1]", str(counter).zfill(1))
        file_name = file_name.replace("[NUM-2]", str(counter).zfill(2))
        file_name = file_name.replace("[NUM-3]", str(counter).zfill(3))
        file_name = file_name.replace("[NUM-4]", str(counter).zfill(4))
        file_name = file_name.replace("[NUM-5]", str(counter).zfill(5))
        return file_name

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

        # Save the data in a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temporary_file:
            logging.debug("    Creating temp file {}".format(temporary_file.name))
            doc.write(temporary_file.name)
            return temporary_file.name

    def get_layers(self, file, skip_hidden_layers, use_background_layers):
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
            if use_background_layers and layer_label.lower().startswith("[fixed] "):
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
