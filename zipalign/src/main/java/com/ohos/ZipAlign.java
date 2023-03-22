/*
 * Copyright (c) 2023 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.ohos;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.TimeZone;
import java.util.zip.ZipOutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Zip align
 *
 * @since 2023-2-20
 */
public class ZipAlign {
    private static final long TIMESTAMP = 1230768000000L;
    private static final int COMPRESSION_MODE = 0;
    private static final int STORED_ENTRY_SO_ALIGNMENT = 4096;
    private static final int BUFFER_LENGTH = 4096;
    private static final long INIT_OFFSET_LEN = 0L;

    private static void copyFileAndAlignment(File input, File tmpOutput, int alignment) throws IOException {
        try (ZipFile inputZip = new ZipFile(input);
                FileOutputStream outputFile = new FileOutputStream(tmpOutput);
                ZipOutputStream outputZip = new ZipOutputStream(outputFile)) {
            long timestamp = TIMESTAMP;
            timestamp -= TimeZone.getDefault().getOffset(timestamp);
            outputZip.setLevel(COMPRESSION_MODE);
            List<String> entryNames = getEntryNamesFromZip(inputZip);
            copyFiles(entryNames, inputZip, outputZip, timestamp, alignment);
        }
    }

    private static void copyFiles(List<String> entryNames, ZipFile in, ZipOutputStream out, long timestamp,
            int defaultAlignment) throws IOException {
        Collections.sort(entryNames);
        long offset = INIT_OFFSET_LEN;
        for (String name : entryNames) {
            ZipEntry inEntry = in.getEntry(name);
            if (inEntry.getMethod() != ZipEntry.STORED) {
                continue;
            }

            offset += ZipFile.LOCHDR;

            ZipEntry outEntry = new ZipEntry(inEntry);
            outEntry.setTime(timestamp);

            outEntry.setComment(null);
            outEntry.setExtra(null);

            offset += outEntry.getName().length();

            int alignment = getStoredEntryDataAlignment(name, defaultAlignment);
            if (alignment > 0 && (offset % alignment != 0)) {
                int needed = alignment - (int) (offset % alignment);
                outEntry.setExtra(new byte[needed]);
                offset += needed;
            }

            out.putNextEntry(outEntry);
            byte[] buffer = new byte[BUFFER_LENGTH];
            try (InputStream data = in.getInputStream(inEntry)) {
                int num;
                while ((num = data.read(buffer)) > 0) {
                    out.write(buffer, 0, num);
                    offset += num;
                }
                out.flush();
            }
        }
    }

    private static int getStoredEntryDataAlignment(String entryName, int defaultAlignment) {
        if (defaultAlignment <= 0) {
            return 0;
        }
        if (entryName.endsWith(".so")) {
            return STORED_ENTRY_SO_ALIGNMENT;
        }
        return defaultAlignment;
    }

    private static List<String> getEntryNamesFromZip(ZipFile zipFile) {
        List<String> result = new ArrayList<String>();
        for (Enumeration e = zipFile.entries(); e.hasMoreElements();) {
            Object nextEntry = e.nextElement();
            if (nextEntry instanceof ZipEntry) {
                ZipEntry entry = (ZipEntry) nextEntry;
                if (!entry.isDirectory()) {
                    result.add(entry.getName());
                }
            }
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println("copyFileAndAlignment start");
        if (args.length != 3) {
            System.out.println("input param error");
            return;
        }
        String inputFilePath = args[0];
        File inputFile = new File(inputFilePath);
        String outputFilePath = args[1];
        File outputFile = new File(outputFilePath);
        try {
            int alignment = Integer.parseInt(args[2]);
            copyFileAndAlignment(inputFile, outputFile, alignment);
        } catch (NumberFormatException nfe) {
            System.out.println("alignment parse error: " + args[2]);
        } catch (IOException ioe) {
            System.out.println(ioe.getMessage());
        }
        System.out.println("copyFileAndAlignment success");
    }
}