"""EELS Quantification objects.
"""
import copy
import functools
import gettext
import typing
import uuid

from nion.data import Calibration
from nion.eels_analysis import PeriodicTable
from nion.swift.model import DataItem
from nion.swift.model import DataStructure
from nion.swift.model import DisplayItem
from nion.swift.model import DocumentModel
from nion.swift.model import Graphics
from nion.swift.model import Symbolic
from nion.utils import Binding
from nion.utils import Event
from nion.utils import ListModel
from nion.utils import Observable


_ = gettext.gettext


class EELSInterval:
    """An interval value object."""

    def __init__(self, start_ev: float=None, end_ev: float=None):
        super().__init__()
        self.__start_ev = start_ev
        self.__end_ev = end_ev

    @staticmethod
    def from_fractional_interval(data_len: int, calibration: Calibration.Calibration, interval: typing.Tuple[float, float]) -> "EELSInterval":
        assert data_len > 0
        start_pixel, end_pixel = interval[0] * data_len, interval[1] * data_len
        return EELSInterval(start_ev=calibration.convert_to_calibrated_value(start_pixel), end_ev=calibration.convert_to_calibrated_value(end_pixel))

    @staticmethod
    def from_d(d: typing.Dict) -> "EELSInterval":
        start_ev = (d or dict()).get("start_ev", None)
        end_ev = (d or dict()).get("end_ev", None)
        return EELSInterval(start_ev, end_ev)

    @property
    def start_ev(self) -> typing.Optional[float]:
        return self.__start_ev

    @start_ev.setter
    def start_ev(self, value: typing.Optional[float]) -> None:
        self.__start_ev = value

    @property
    def end_ev(self) -> typing.Optional[float]:
        return self.__end_ev

    @end_ev.setter
    def end_ev(self, value: typing.Optional[float]) -> None:
        self.__end_ev = value

    @property
    def width_ev(self) -> typing.Optional[float]:
        if self.start_ev is not None and self.end_ev is not None:
            return self.end_ev - self.start_ev
        return None

    def to_fractional_interval(self, data_len: int, calibration: Calibration.Calibration) -> typing.Tuple[float, float]:
        assert data_len > 0
        start_pixel = calibration.convert_from_calibrated_value(self.start_ev)
        end_pixel = calibration.convert_from_calibrated_value(self.end_ev)
        return start_pixel / data_len, end_pixel / data_len

    def _write_to_dict(self) -> typing.Dict:
        d = dict()
        if self.__start_ev is not None:
            d["start_ev"] = self.start_ev
        if self.__end_ev is not None:
            d["end_ev"] = self.end_ev
        return d


class EELSInterfaceToFractionalIntervalConverter:
    def __init__(self, eels_data_len: int, eels_calibration: Calibration.Calibration):
        self.__eels_data_len = eels_data_len
        self.__eels_calibration = eels_calibration

    def convert(self, eels_interval: EELSInterval) -> typing.Tuple[float, float]:
        return eels_interval.to_fractional_interval(self.__eels_data_len, self.__eels_calibration)

    def convert_back(self, interval: typing.Tuple[float, float]) -> EELSInterval:
        return EELSInterval.from_fractional_interval(self.__eels_data_len, self.__eels_calibration, interval)


class EELSEdge(Observable.Observable):
    """An edge is a signal interval, a list of fit intervals, and other edge identifying information."""

    def __init__(self, *, signal_eels_interval: EELSInterval=None, fit_eels_intervals: typing.List[EELSInterval]=None, electron_shell: PeriodicTable.ElectronShell=None, d: typing.Dict=None):
        super().__init__()
        self.__uuid = uuid.uuid4()
        self.__signal_eels_interval = signal_eels_interval
        self.__fit_eels_intervals = fit_eels_intervals or list()
        self.__electron_shell = electron_shell
        self.fit_eels_interval_changed = Event.Event()
        if d is not None:
            self.__uuid = uuid.UUID(d.get("uuid", str(uuid.uuid4())))
            self.__signal_eels_interval = EELSInterval.from_d(d.get("signal_eels_interval"))
            self.__fit_eels_intervals = [EELSInterval.from_d(fit_interval_d) for fit_interval_d in d.get("fit_eels_intervals", list())]
            self.__electron_shell = PeriodicTable.ElectronShell.from_d(d.get("electron_shell"))

    @property
    def uuid(self) -> uuid.UUID:
        return self.__uuid

    @property
    def signal_eels_interval(self) -> typing.Optional[EELSInterval]:
        return self.__signal_eels_interval

    @signal_eels_interval.setter
    def signal_eels_interval(self, value: typing.Optional[EELSInterval]) -> None:
        self.__signal_eels_interval = value
        self.notify_property_changed("signal_eels_interval")

    @property
    def electron_shell(self) -> typing.Optional[PeriodicTable.ElectronShell]:
        return self.__electron_shell

    @electron_shell.setter
    def electron_shell(self, value: typing.Optional[PeriodicTable.ElectronShell]) -> None:
        self.__signal_eels_interval = value
        self.notify_property_changed("electron_shell")

    def insert_fit_eels_interval(self, index: int, interval: EELSInterval) -> None:
        self.__fit_eels_intervals.insert(index, interval)
        self.notify_insert_item("fit_eels_intervals", interval, index)

    def append_fit_eels_interval(self, interval: EELSInterval) -> None:
        self.insert_fit_eels_interval(len(self.__fit_eels_intervals), interval)

    def remove_fit_eels_interval(self, index: int) -> None:
        fit_interval = self.__fit_eels_intervals[index]
        self.__fit_eels_intervals.remove(fit_interval)
        self.notify_remove_item("fit_eels_intervals", fit_interval, index)

    def set_fit_eels_interval(self, index: int, interval: EELSInterval) -> None:
        self.__fit_eels_intervals[index] = interval
        self.notify_item_value_changed("fit_eels_intervals", interval, index)

    @property
    def fit_eels_intervals(self) -> typing.List[EELSInterval]:
        return self.__fit_eels_intervals

    def _write_to_dict(self) -> typing.Dict:
        d = {"uuid": str(self.__uuid)}
        if self.__signal_eels_interval:
            d["signal_eels_interval"] = self.__signal_eels_interval._write_to_dict()
        if len(self.__fit_eels_intervals) > 0:
            d["fit_eels_intervals"] = [fit_eels_interval._write_to_dict() for fit_eels_interval in self.__fit_eels_intervals]
        if self.__signal_eels_interval:
            d["signal_eels_interval"] = self.__signal_eels_interval._write_to_dict()
        if self.__electron_shell:
            d["electron_shell"] = self.__electron_shell._write_to_dict()
        return d


class EELSQuantification(Observable.Observable):
    """Quantification settings include a list of edges."""

    def __init__(self, document_model: DocumentModel.DocumentModel, data_structure: DataStructure.DataStructure):
        super().__init__()
        self.__document_model = document_model
        self.__eels_edges = list()
        self.__data_structure = data_structure
        self.__read()

    def destroy(self) -> None:
        while len(self.__eels_edges) > 0:
            eels_edge = self.__eels_edges[-1]
            self.__eels_edges.remove(eels_edge)
            self.notify_remove_item("eels_edges", eels_edge, len(self.__eels_edges))
        if self.__data_structure:
            self.__document_model.remove_data_structure(self.__data_structure)
        self.__data_structure = None

    def _data_structure_deleted(self):
        self.__data_structure = None

    @property
    def document_model(self) -> DocumentModel.DocumentModel:
        return self.__document_model

    @property
    def data_structure(self) -> DataStructure.DataStructure:
        return self.__data_structure

    def insert_edge(self, index: int, eels_edge: EELSEdge) -> None:
        self.__eels_edges.insert(index, eels_edge)
        self.notify_insert_item("eels_edges", eels_edge, index)
        self.__write()

    def append_edge(self, eels_edge: EELSEdge) -> None:
        self.insert_edge(len(self.__eels_edges), eels_edge)

    def remove_edge(self, index: int) -> None:
        eels_edge = self.__eels_edges[index]
        self.__eels_edges.remove(eels_edge)
        self.notify_remove_item("eels_edges", eels_edge, index)
        self.__write()

    @property
    def eels_edges(self) -> typing.List[EELSEdge]:
        return self.__eels_edges

    def get_eels_edge_from_uuid(self, eels_edge_uuid: uuid.UUID) -> typing.Optional[EELSEdge]:
        for eels_edge in self.eels_edges:
            if eels_edge.uuid == eels_edge_uuid:
                return eels_edge
        return None

    def __write(self) -> None:
        self.__data_structure.set_property_value("eels_edges", [eels_edge._write_to_dict() for eels_edge in self.eels_edges])

    def __read(self) -> None:
        for eels_edge_d in self.__data_structure.get_property_value("eels_edges", list()):
            self.__eels_edges.append(EELSEdge(d=eels_edge_d))


class EELSEdgeDisplay:

    def __init__(self, eels_edge: EELSEdge, should_hide_fn):
        self.__eels_edge = eels_edge
        self.__should_hide_fn = should_hide_fn
        self.background_data_item = None
        self.signal_data_item = None
        self.signal_interval_graphic = None
        self.fit_interval_graphics = list()
        self.computation = None
        self.__signal_interval_connection = None
        self.__interval_list_connection = None
        self.__signal_interval_about_to_close_connection = None
        self.__computation_about_to_close_connection = None

    def close(self):
        if self.__signal_interval_connection:
            self.__signal_interval_connection.close()
            self.__signal_interval_connection = None
        if self.__interval_list_connection:
            self.__interval_list_connection.close()
            self.__interval_list_connection = None
        if self.__signal_interval_about_to_close_connection:
            self.__signal_interval_about_to_close_connection.close()
            self.__signal_interval_about_to_close_connection = None
        if self.__computation_about_to_close_connection:
            self.__computation_about_to_close_connection.close()
            self.__computation_about_to_close_connection = None

    @property
    def eels_edge(self) -> EELSEdge:
        return self.__eels_edge

    def show(self, document_model: DocumentModel.DocumentModel, eels_display_item: DisplayItem.DisplayItem, eels_data_item: DataItem.DataItem) -> None:

        # create new data items for signal and background, add them to the document model
        if self.signal_data_item:
            signal_data_item = self.signal_data_item
        else:
            signal_data_item = DataItem.DataItem()
            document_model.append_data_item(signal_data_item, auto_display=False)
            signal_data_item.title = f"{eels_data_item.title} Signal"
        if self.background_data_item:
            background_data_item = self.background_data_item
        else:
            background_data_item = DataItem.DataItem()
            document_model.append_data_item(background_data_item, auto_display=False)
            background_data_item.title = f"{eels_data_item.title} Background"

        # create display data channels and display layers for signal and background
        background_display_data_channel = eels_display_item.get_display_data_channel_for_data_item(background_data_item)
        if not background_display_data_channel:
            eels_display_item.append_display_data_channel(DisplayItem.DisplayDataChannel(background_data_item))
            background_display_data_channel = eels_display_item.get_display_data_channel_for_data_item(background_data_item)
            background_data_item_index = eels_display_item.display_data_channels.index(background_display_data_channel)
            eels_display_item.insert_display_layer(0, data_index=background_data_item_index)
            eels_display_item._set_display_layer_property(0, "label", _("Background"))
            eels_display_item._set_display_layer_property(0, "fill_color", "rgba(255, 0, 0, 0.3)")

        signal_display_data_channel = eels_display_item.get_display_data_channel_for_data_item(signal_data_item)
        if not signal_display_data_channel:
            eels_display_item.append_display_data_channel(DisplayItem.DisplayDataChannel(signal_data_item))
            signal_display_data_channel = eels_display_item.get_display_data_channel_for_data_item(signal_data_item)
            signal_data_item_index = eels_display_item.display_data_channels.index(signal_display_data_channel)
            eels_display_item.insert_display_layer(0, data_index=signal_data_item_index)
            eels_display_item._set_display_layer_property(0, "label", _("Signal"))
            eels_display_item._set_display_layer_property(0, "fill_color", "lime")

        # useful values
        eels_data_len = eels_data_item.data_shape[-1]
        eels_calibration = eels_data_item.dimensional_calibrations[-1]

        # create the signal interval graphic
        if self.signal_interval_graphic:
            signal_interval_graphic = self.signal_interval_graphic
        else:
            signal_interval_graphic = Graphics.IntervalGraphic()
            signal_interval_graphic.interval = self.__eels_edge.signal_eels_interval.to_fractional_interval(eels_data_len, eels_calibration)
            eels_display_item.add_graphic(signal_interval_graphic)

        # watch for signal graphic being deleted and treat it like hiding
        if self.__signal_interval_about_to_close_connection:
            self.__signal_interval_about_to_close_connection.close()
            self.__signal_interval_about_to_close_connection = None

        def signal_interval_graphic_removed(cascade_items: typing.List) -> None:
            self.signal_interval_graphic = None
            self.__should_hide_fn(self)

        self.__signal_interval_about_to_close_connection = signal_interval_graphic.about_to_cascade_delete_event.listen(signal_interval_graphic_removed)

        # bind signal interval graphic to signal interval
        if self.__signal_interval_connection:
            self.__signal_interval_connection.close()
            self.__signal_interval_connection = None
        self.__signal_interval_connection = IntervalConnection(eels_data_item, self.__eels_edge, "signal_eels_interval", signal_interval_graphic)

        # create the fit interval graphics
        fit_interval_graphics = self.fit_interval_graphics
        for index, fit_eels_interval in enumerate(self.__eels_edge.fit_eels_intervals):
            if len(fit_interval_graphics) <= index:
                fit_interval_graphic = Graphics.IntervalGraphic()
                eels_display_item.add_graphic(fit_interval_graphic)
                fit_interval_graphics.append(fit_interval_graphic)
            else:
                fit_interval_graphic = fit_interval_graphics[index]
            fit_interval_graphic.interval = fit_eels_interval.to_fractional_interval(eels_data_len, eels_calibration)

        # create the computation to compute background and signal
        if self.computation:
            computation = self.computation
        else:
            computation = document_model.create_computation()
            computation.processing_id = "eels.background_subtraction2"
            computation.source = eels_display_item
            computation.create_variable("eels_edge_uuid", "string", str(self.eels_edge.uuid))
            computation.create_object("eels_spectrum_data_item", document_model.get_object_specifier(eels_data_item))
            computation.create_objects("fit_interval_graphics", [document_model.get_object_specifier(fit_interval_graphic) for fit_interval_graphic in fit_interval_graphics])
            computation.create_object("signal_interval_graphic", document_model.get_object_specifier(signal_interval_graphic))
            computation.create_result("subtracted", document_model.get_object_specifier(signal_data_item))
            computation.create_result("background", document_model.get_object_specifier(background_data_item))
            document_model.append_computation(computation)

        # bind fit interval graphics to fit intervals
        if self.__interval_list_connection:
            self.__interval_list_connection.close()
            self.__interval_list_connection = None

        self.__interval_list_connection = IntervalListConnection(document_model, eels_display_item, eels_data_item, self.__eels_edge, fit_interval_graphics, computation)

        # watch for computation being removed
        if self.__computation_about_to_close_connection:
            self.__computation_about_to_close_connection.close()
            self.__computation_about_to_close_connection = None

        def computation_removed(cascade_items: typing.List) -> None:
            self.computation = None
            # computation will delete the two data items
            self.background_data_item = None
            self.signal_data_item = None
            self.__should_hide_fn(self)

        self.__computation_about_to_close_connection = computation.about_to_cascade_delete_event.listen(computation_removed)

        # enable the legend display
        eels_display_item.set_display_property("legend_position", "top-right")

        # store values
        self.background_data_item = background_data_item
        self.signal_data_item = signal_data_item
        self.signal_interval_graphic = signal_interval_graphic
        self.fit_interval_graphics = fit_interval_graphics
        self.computation = computation

    def hide(self, document_model: DocumentModel.DocumentModel, eels_display_item: DisplayItem.DisplayItem) -> None:
        if self.__signal_interval_connection:
            self.__signal_interval_connection.close()
            self.__signal_interval_connection = None
        if self.__interval_list_connection:
            self.__interval_list_connection.close()
            self.__interval_list_connection = None
        if self.__signal_interval_about_to_close_connection:
            self.__signal_interval_about_to_close_connection.close()
            self.__signal_interval_about_to_close_connection = None
        if self.__computation_about_to_close_connection:
            self.__computation_about_to_close_connection.close()
            self.__computation_about_to_close_connection = None
        if self.computation:
            document_model.remove_computation(self.computation)
            self.computation = None
        if self.signal_interval_graphic:
            eels_display_item.remove_graphic(self.signal_interval_graphic)
            self.signal_interval_graphic = None
        for graphic in self.fit_interval_graphics:
            eels_display_item.remove_graphic(graphic)
        self.fit_interval_graphics = list()
        # these items should auto remove with the computation
        if self.background_data_item in document_model.data_items:
            document_model.remove_data_item(self.background_data_item)
            self.background_data_item = None
        if self.signal_data_item in document_model.data_items:
            document_model.remove_data_item(self.signal_data_item)
            self.signal_data_item = None


class EELSQuantificationDisplay(Observable.Observable):
    """Display settings for an EELS quantification."""

    def __init__(self, eels_quantification: EELSQuantification, data_structure: DataStructure.DataStructure, should_remove_fn):
        super().__init__()

        self.__data_structure = data_structure
        self.__eels_quantification = eels_quantification
        self.__should_remove_fn = should_remove_fn
        self.__document_model = eels_quantification.document_model
        self.eels_display_item = None
        self.eels_data_item = None
        self.__eels_edge_displays = list()

        self.__read()

        def eels_edge_removed(key: str, value, index: int) -> None:
            if key == "eels_edges":
                eels_edge = value
                eels_edge_display = self.get_eels_edge_display_for_eels_edge(eels_edge)
                if eels_edge_display:
                    self.__should_hide(eels_edge_display)

        self.__eels_quantification_item_removed_event_listener = self.__eels_quantification.item_removed_event.listen(eels_edge_removed)

    def close(self):
        self.__eels_quantification_item_removed_event_listener.close()
        self.__eels_quantification_item_removed_event_listener = None
        if self.__eels_data_item_about_to_be_removed_event_listener:
            self.__eels_data_item_about_to_be_removed_event_listener.close()
            self.__eels_data_item_about_to_be_removed_event_listener = None
        if self.__eels_display_item_about_to_be_removed_event_listener:
            self.__eels_display_item_about_to_be_removed_event_listener.close()
            self.__eels_display_item_about_to_be_removed_event_listener = None

    @property
    def document_model(self) -> DocumentModel.DocumentModel:
        return self.__document_model

    @property
    def data_structure(self) -> DataStructure.DataStructure:
        return self.__data_structure

    @property
    def eels_quantification(self) -> EELSQuantification:
        return self.__eels_quantification

    @property
    def eels_edge_displays(self) -> typing.List[EELSEdgeDisplay]:
        return self.__eels_edge_displays

    def get_eels_edge_display_for_eels_edge(self, eels_edge: EELSEdge) -> typing.Optional[EELSEdgeDisplay]:
        for eels_edge_display in self.__eels_edge_displays:
            if eels_edge_display.eels_edge == eels_edge:
                return eels_edge_display
        return None

    def __write(self) -> None:
        self.__data_structure.set_property_value("eels_edge_displays", [{"eels_edge_uuid": str(eels_edge_display.eels_edge.uuid)} for eels_edge_display in self.__eels_edge_displays])
        self.__data_structure.set_referenced_object("eels_display_item", self.eels_display_item)
        self.__data_structure.set_referenced_object("eels_data_item", self.eels_data_item)

    def __read(self) -> None:
        self.eels_data_item = self.__data_structure.get_referenced_object("eels_data_item")
        self.eels_display_item = self.__data_structure.get_referenced_object("eels_display_item")

        def notify_remove(cascade_items: typing.List) -> None:
            self.__should_remove_fn(self)

        self.__eels_data_item_about_to_be_removed_event_listener = self.eels_data_item.about_to_cascade_delete_event.listen(notify_remove) if self.eels_data_item else None
        self.__eels_display_item_about_to_be_removed_event_listener = self.eels_display_item.about_to_cascade_delete_event.listen(notify_remove) if self.eels_display_item else None

        computation_map = dict()
        for computation in self.__document_model.computations:
            if computation.processing_id == "eels.background_subtraction2" and computation.source == self.eels_display_item:
                eels_edge_uuid_var = computation._get_variable("eels_edge_uuid")
                if eels_edge_uuid_var:
                    computation_map[uuid.UUID(eels_edge_uuid_var.value)] = computation

        eels_edge_display_d_list = self.__data_structure.get_property_value("eels_edge_displays", list())
        for eels_edge_display_d in eels_edge_display_d_list:
            eels_edge_uuid = uuid.UUID(eels_edge_display_d.get("eels_edge_uuid", str(uuid.uuid4())))
            if eels_edge_uuid in computation_map:
                computation = computation_map.pop(eels_edge_uuid)
                fit_interval_graphics = computation._get_variable("fit_interval_graphics").bound_item.value
                signal_interval_graphic = computation._get_variable("signal_interval_graphic").bound_item.value
                subtracted_data_item = computation.get_referenced_object("subtracted")
                background_data_item = computation.get_referenced_object("background")
                eels_edge = self.__eels_quantification.get_eels_edge_from_uuid(eels_edge_uuid)
                assert eels_edge is not None
                eels_edge_display = EELSEdgeDisplay(eels_edge, self.__should_hide)
                eels_edge_display.computation = computation
                eels_edge_display.fit_interval_graphics = fit_interval_graphics
                eels_edge_display.signal_interval_graphic = signal_interval_graphic
                eels_edge_display.background_data_item = background_data_item
                eels_edge_display.signal_data_item = subtracted_data_item
                self.__eels_edge_displays.append(eels_edge_display)

    def __should_hide(self, eels_edge_display: EELSEdgeDisplay) -> None:
        eels_edge_display.hide(self.__document_model, self.eels_display_item)
        self.__eels_edge_displays.remove(eels_edge_display)
        self.__write()

    def __should_show(self, eels_edge_display: EELSEdgeDisplay) -> None:
        self.__eels_edge_displays.append(eels_edge_display)
        self.__write()
        eels_edge_display.show(self.__document_model, self.eels_display_item, self.eels_data_item)

    def destroy(self) -> None:
        for eels_edge_display in self.__eels_edge_displays:
            eels_edge_display.hide(self.__document_model, self.eels_display_item)
        self.__eels_edge_displays.clear()
        self.__document_model.remove_data_structure(self.__data_structure)
        self.__data_structure = None

    def add_eels_edge(self, eels_edge: EELSEdge) -> None:
        self.__eels_quantification.append_edge(eels_edge)

    def remove_eels_edge(self, eels_edge: EELSEdge) -> None:
        self.__eels_quantification.remove_edge(self.__eels_quantification.eels_edges.index(eels_edge))

    def add_eels_edge_from_interval_graphic(self, signal_interval_graphic: Graphics.IntervalGraphic) -> EELSEdge:
        # get the fractional signal interval from the graphic
        signal_interval = signal_interval_graphic.interval

        # calculate fit intervals ahead and behind the signal
        fit_ahead_interval = signal_interval[0] * 0.8, signal_interval[0] * 0.9
        fit_behind_interval = signal_interval[1] * 1.1, signal_interval[1] * 1.2

        # get length and calibration values from the EELS data item
        eels_data_len = self.eels_data_item.data_shape[-1]
        eels_data_calibration = self.eels_data_item.dimensional_calibrations[-1]

        # create the signal and two fit EELS intervals
        signal_eels_interval = EELSInterval.from_fractional_interval(eels_data_len, eels_data_calibration, signal_interval)
        fit_ahead_eels_interval = EELSInterval.from_fractional_interval(eels_data_len, eels_data_calibration, fit_ahead_interval)
        fit_behind_eels_interval = EELSInterval.from_fractional_interval(eels_data_len, eels_data_calibration, fit_behind_interval)

        # create the EELS edge object
        eels_edge = EELSEdge(signal_eels_interval=signal_eels_interval, fit_eels_intervals=[fit_ahead_eels_interval, fit_behind_eels_interval])

        # add the EELS edge object to the quantification object
        self.__eels_quantification.append_edge(eels_edge)

        # show the edge
        eels_edge_display = EELSEdgeDisplay(eels_edge, self.__should_hide)
        eels_edge_display.signal_interval_graphic = signal_interval_graphic
        self.__should_show(eels_edge_display)

        # return the edge
        return eels_edge

    def hide_eels_edge(self, eels_edge: EELSEdge) -> None:
        eels_edge_display = self.get_eels_edge_display_for_eels_edge(eels_edge)
        if eels_edge_display:
            self.__should_hide(eels_edge_display)

    def show_eels_edge(self, eels_edge: EELSEdge) -> None:
        eels_edge_display = self.get_eels_edge_display_for_eels_edge(eels_edge)
        if not eels_edge_display:
            assert eels_edge in self.__eels_quantification.eels_edges
            eels_edge_display = EELSEdgeDisplay(eels_edge, self.__should_hide)
            self.__should_show(eels_edge_display)

    def is_eels_edge_visible(self, eels_edge: EELSEdge) -> bool:
        eels_edge_display = self.get_eels_edge_display_for_eels_edge(eels_edge)
        return eels_edge_display is not None


class Singleton(type):
    def __init__(cls, name, bases, dict):
        super().__init__(name, bases, dict)
        cls.instance = None

    def __call__(cls, *args, **kw):
        if cls.instance is None:
            cls.instance = super().__call__(*args, **kw)
        return cls.instance


class EELSQuantificationManager:
    instances = dict()
    listeners = dict()

    @classmethod
    def get_instance(cls, document_model: DocumentModel.DocumentModel) -> "EELSQuantificationManager":
        if not document_model in cls.instances:
            cls.instances[document_model] = EELSQuantificationManager(document_model)

            def document_about_to_close():
                cls.instances.pop(document_model)
                cls.listeners.pop(document_model)

            cls.listeners[document_model] = document_model.about_to_close_event.listen(document_about_to_close)

        return cls.instances[document_model]

    def __init__(self, document_model: DocumentModel.DocumentModel):
        self.__document_model = document_model

        self.__eels_quantifications = list()
        self.__eels_quantification_list_model = ListModel.FilteredListModel(container=self.__document_model, master_items_key="data_structures", items_key="eels_quantification_data_structures")
        self.__eels_quantification_list_model.filter = ListModel.EqFilter("structure_type", "nion.eels_quantification")

        def eels_quantification_list_item_inserted(key: str, value: DataStructure.DataStructure, before_index: int) -> None:
            self.__eels_quantifications.insert(before_index, EELSQuantification(self.__document_model, value))

        def eels_quantification_list_item_removed(key: str, value: DataStructure.DataStructure, index: int) -> None:
            for eels_quantification in self.__eels_quantifications:
                if eels_quantification.data_structure == value:
                    eels_quantification._data_structure_deleted()
                    self.destroy_eels_quantification(eels_quantification)
            self.__eels_quantifications.pop(index)

        self.__eels_quantification_list_item_inserted_event_listener = self.__eels_quantification_list_model.item_inserted_event.listen(eels_quantification_list_item_inserted)
        self.__eels_quantification_list_item_removed_event_listener = self.__eels_quantification_list_model.item_removed_event.listen(eels_quantification_list_item_removed)

        for index, eels_quantification in enumerate(self.__eels_quantification_list_model.items):
            eels_quantification_list_item_inserted("eels_quantification_data_structures", eels_quantification, index)

        self.__eels_quantification_displays = list()
        self.__eels_quantification_display_list_model = ListModel.FilteredListModel(container=self.__document_model, master_items_key="data_structures", items_key="eels_quantification_display_data_structures")
        self.__eels_quantification_display_list_model.filter = ListModel.EqFilter("structure_type", "nion.eels_quantification_display")

        def eels_quantification_display_list_item_inserted(key: str, value: DataStructure.DataStructure, before_index: int) -> None:
            data_structure = value
            eels_quantification = None
            for eels_quantification_ in self.__eels_quantifications:
                if eels_quantification_.data_structure == value.source:
                    eels_quantification = eels_quantification_
                    break

            def should_remove(eels_quantification_display: EELSQuantificationDisplay) -> None:
                if eels_quantification_display in self.get_eels_quantification_displays(eels_quantification):
                    self.destroy_eels_quantification_display(eels_quantification_display)

            self.__eels_quantification_displays.insert(before_index, EELSQuantificationDisplay(eels_quantification, data_structure, should_remove))

        def eels_quantification_display_list_item_removed(key: str, value: DataStructure.DataStructure, index: int) -> None:
            self.__eels_quantification_displays.pop(index)

        self.__eels_quantification_display_list_item_inserted_event_listener = self.__eels_quantification_display_list_model.item_inserted_event.listen(eels_quantification_display_list_item_inserted)
        self.__eels_quantification_display_list_item_removed_event_listener = self.__eels_quantification_display_list_model.item_removed_event.listen(eels_quantification_display_list_item_removed)

        for index, eels_quantification_display in enumerate(self.__eels_quantification_display_list_model.items):
            eels_quantification_display_list_item_inserted("eels_quantification_display_data_structures", eels_quantification_display, index)

    def close(self) -> None:
        self.__eels_quantification_list_item_inserted_event_listener.close()
        self.__eels_quantification_list_item_inserted_event_listener = None
        self.__eels_quantification_list_item_removed_event_listener.close()
        self.__eels_quantification_list_item_removed_event_listener = None
        self.__eels_quantification_list_model.close()
        self.__eels_quantification_list_model = None
        self.__eels_quantification_display_list_item_inserted_event_listener.close()
        self.__eels_quantification_display_list_item_inserted_event_listener = None
        self.__eels_quantification_display_list_item_removed_event_listener.close()
        self.__eels_quantification_display_list_item_removed_event_listener = None
        self.__eels_quantification_display_list_model.close()
        self.__eels_quantification_display_list_model = None

    @property
    def eels_quantifications(self) -> typing.List[EELSQuantification]:
        return self.__eels_quantifications

    def create_eels_quantification(self) -> EELSQuantification:
        data_structure = DataStructure.DataStructure(structure_type="nion.eels_quantification")
        self.__document_model.append_data_structure(data_structure)
        for eels_quantification in self.__eels_quantifications:
            if eels_quantification.data_structure == data_structure:
                return eels_quantification
        # should never reach this point since object is created automatically by inserting data structure into document model
        return EELSQuantification(self.__document_model, data_structure)

    def destroy_eels_quantification(self, eels_quantification: EELSQuantification) -> None:
        for eels_quantification_display in copy.copy(self.get_eels_quantification_displays(eels_quantification)):
            self.destroy_eels_quantification_display(eels_quantification_display)
        eels_quantification.destroy()

    def create_eels_quantification_display(self, eels_quantification: EELSQuantification, eels_display_item: DisplayItem.DisplayItem, eels_data_item: DataItem.DataItem) -> EELSQuantificationDisplay:
        data_structure = DataStructure.DataStructure(structure_type="nion.eels_quantification_display", source=eels_quantification.data_structure)
        data_structure.set_referenced_object("eels_display_item", eels_display_item)
        data_structure.set_referenced_object("eels_data_item", eels_data_item)
        self.__document_model.append_data_structure(data_structure)
        for eels_quantification_display in self.get_eels_quantification_displays(eels_quantification):
            if eels_quantification_display.data_structure == data_structure:
                return eels_quantification_display
        # should never reach this point since object is created automatically by inserting data structure into document model
        return EELSQuantificationDisplay(eels_quantification, data_structure, None)

    def destroy_eels_quantification_display(self, eels_quantification_display: EELSQuantificationDisplay) -> None:
        eels_quantification_display.destroy()
        eels_quantification_display.close()

    def get_eels_quantification_displays(self, eels_quantification: EELSQuantification) -> typing.List[EELSQuantificationDisplay]:
        return [eels_quantification_display for eels_quantification_display in self.__eels_quantification_displays if eels_quantification_display.eels_quantification == eels_quantification]


class IntervalConnection:

    def __init__(self, eels_data_item: DataItem.DataItem, eels_edge: EELSEdge, interval_property_name: str, interval_graphic: Graphics.IntervalGraphic):
        self.__interval_graphic_listener = None
        self.__interval_binding = None

        eels_data_len = eels_data_item.data_shape[-1]
        eels_calibration = eels_data_item.dimensional_calibrations[-1]

        converter = EELSInterfaceToFractionalIntervalConverter(eels_data_len, eels_calibration)
        interval_binding = Binding.PropertyBinding(eels_edge, interval_property_name, converter=converter)

        def update_interval(interval):
            interval_graphic.interval = interval

        interval_binding.target_setter = update_interval

        blocked = [False]
        def update_eels_interval(property_name):
            if property_name == "interval" and not blocked[0]:
                blocked[0] = True
                interval_binding.update_source(interval_graphic.interval)
                blocked[0] = False

        self.__interval_graphic_listener = interval_graphic.property_changed_event.listen(update_eels_interval)
        self.__interval_binding = interval_binding

    def close(self):
        if self.__interval_graphic_listener:
            self.__interval_graphic_listener.close()
            self.__interval_graphic_listener = None
        if self.__interval_binding:
            self.__interval_binding.close()
            self.__interval_binding = None


class IntervalListConnection:

    def __init__(self, document_model: DocumentModel.DocumentModel, eels_display_item: DisplayItem.DisplayItem, eels_data_item: DataItem.DataItem, eels_edge: EELSEdge, fit_interval_graphics: typing.List[Graphics.IntervalGraphic], computation: Symbolic.Computation):
        self.__fit_interval_graphic_property_changed_listeners = list()
        self.__fit_interval_graphic_about_to_be_removed_listeners = list()
        self.__fit_interval_graphics = fit_interval_graphics

        eels_data_len = eels_data_item.data_shape[-1]
        eels_calibration = eels_data_item.dimensional_calibrations[-1]

        converter = EELSInterfaceToFractionalIntervalConverter(eels_data_len, eels_calibration)

        blocked = [False]
        def update_fit_eels_interval(index: int, property_name: str) -> None:
            if property_name == "interval" and not blocked[0]:
                blocked[0] = True
                eels_edge.set_fit_eels_interval(index, converter.convert_back(self.__fit_interval_graphics[index].interval))
                blocked[0] = False

        remove_blocked = [False]  # argh.
        def remove_fit_eels_interval(index: int, cascade_items: typing.List) -> None:
            # this message comes from the library.
            remove_blocked[0] = True

            # remove edge; but block notifications are blocked. ugly.
            eels_edge.remove_fit_eels_interval(index)

            # unbind interval graphic from fit eels interval
            self.__fit_interval_graphic_property_changed_listeners[index].close()
            del self.__fit_interval_graphic_property_changed_listeners[index]
            self.__fit_interval_graphic_about_to_be_removed_listeners[index].close()
            del self.__fit_interval_graphic_about_to_be_removed_listeners[index]

            # keep the fit interval graphics list up to date
            del self.__fit_interval_graphics[index]

            remove_blocked[0] = False

        def fit_eels_interval_inserted(key: str, value, before_index: int) -> None:
            # this message comes from the EELS edge
            if key == "fit_eels_intervals":
                fit_eels_interval = value

                # create interval graphic on the display item
                fit_interval_graphic = Graphics.IntervalGraphic()
                eels_display_item.add_graphic(fit_interval_graphic)
                self.__fit_interval_graphics.insert(before_index, fit_interval_graphic)

                # update the interval graphic value
                fit_interval_graphic.interval = fit_eels_interval.to_fractional_interval(eels_data_len, eels_calibration)

                # bind interval graphic to the fit eels interval
                self.__fit_interval_graphic_property_changed_listeners.insert(before_index, fit_interval_graphic.property_changed_event.listen(functools.partial(update_fit_eels_interval, before_index)))
                self.__fit_interval_graphic_about_to_be_removed_listeners.insert(before_index, fit_interval_graphic.about_to_cascade_delete_event.listen(functools.partial(remove_fit_eels_interval, before_index)))

                # add interval graphic to computation
                computation.insert_item_into_objects("fit_interval_graphics", before_index, document_model.get_object_specifier(fit_interval_graphic))

        def fit_eels_interval_removed(key: str, value, index: int) -> None:
            # this message comes from the EELS edge
            if key == "fit_eels_intervals" and not remove_blocked[0]:
                # unbind interval graphic from fit eels interval
                self.__fit_interval_graphic_property_changed_listeners[index].close()
                del self.__fit_interval_graphic_property_changed_listeners[index]
                self.__fit_interval_graphic_about_to_be_removed_listeners[index].close()
                del self.__fit_interval_graphic_about_to_be_removed_listeners[index]

                # remove interval graphic on the display item. this will also remove the graphic from the computation.
                eels_display_item.remove_graphic(self.__fit_interval_graphics[index])

                # keep the fit interval graphics list up to date
                del self.__fit_interval_graphics[index]

        def fit_eels_interval_value_changed(key: str, value, index: int) -> None:
            if key == "fit_eels_intervals":
                fit_eels_interval = value

                # update the associated interval graphic
                self.__fit_interval_graphics[index].interval = converter.convert(fit_eels_interval)

        self.__item_inserted_event_listener = eels_edge.item_inserted_event.listen(fit_eels_interval_inserted)
        self.__item_removed_event_listener = eels_edge.item_removed_event.listen(fit_eels_interval_removed)
        self.__item_value_changed_event_listener = eels_edge.item_value_changed_event.listen(fit_eels_interval_value_changed)

        # initial binding for fit interval graphics

        for index, fit_interval_graphic in enumerate(fit_interval_graphics):
            self.__fit_interval_graphic_property_changed_listeners.insert(index, fit_interval_graphic.property_changed_event.listen(functools.partial(update_fit_eels_interval, index)))
            self.__fit_interval_graphic_about_to_be_removed_listeners.insert(index, fit_interval_graphic.about_to_cascade_delete_event.listen(functools.partial(remove_fit_eels_interval, index)))

    def close(self):
        self.__item_inserted_event_listener.close()
        self.__item_inserted_event_listener = None
        self.__item_removed_event_listener.close()
        self.__item_removed_event_listener = None
        self.__item_value_changed_event_listener.close()
        self.__item_value_changed_event_listener = None

        for interval_graphic_listener in self.__fit_interval_graphic_property_changed_listeners:
            interval_graphic_listener.close()
        self.__fit_interval_graphic_property_changed_listeners = None

        for interval_graphic_listener in self.__fit_interval_graphic_about_to_be_removed_listeners:
            interval_graphic_listener.close()
        self.__fit_interval_graphic_about_to_be_removed_listeners = None
