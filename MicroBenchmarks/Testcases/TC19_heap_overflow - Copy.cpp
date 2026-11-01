// Category: Memory Management Errors
// Error: Heap buffer overflow

#include <iostream>
#include <cstring>

int main() {
    char* buffer = new char[10];
    
    strcpy(buffer, "This string is too long for the buffer");  // ERROR: Heap overflow
    
    std::cout << buffer << std::endl;
    delete[] buffer;
    
    return 0;
}
